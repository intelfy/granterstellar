from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.exceptions import APIException
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.core.mail import send_mail
from django.conf import settings
from .models import Organization, OrgUser, OrgInvite
from .serializers import OrganizationSerializer, OrgUserSerializer, OrgInviteSerializer
from billing.utils import can_admin_add_seat
from billing.quota import get_subscription_for_scope
from .models import OrgProposalAllocation
from django.utils import timezone


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    class ProAdminSingleOrgLimit(APIException):
        status_code = 402
        default_detail = {'error': 'pro_admin_single_org_limit'}
        default_code = 'payment_required'

    def get_queryset(self):
        user = self.request.user
        # Return orgs where user is admin or member
        return Organization.objects.filter(memberships__user=user).distinct()

    def perform_create(self, serializer):
        # Enforce: Pro users can be admins of only a single organization; Enterprise unlimited
        user = self.request.user
        tier, _status = get_subscription_for_scope(user, None)
        if tier == 'pro':
            existing_admin_count = Organization.objects.filter(admin=user).count()
            if existing_admin_count >= 1:
                raise self.ProAdminSingleOrgLimit()
        with transaction.atomic():
            org = serializer.save(admin=user)
            OrgUser.objects.get_or_create(org=org, user=user, defaults={'role': 'admin'})

    def update(self, request, *args: Any, **kwargs: Any):
        org = self.get_object()
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args: Any, **kwargs: Any):
        org = self.get_object()
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='transfer')
    def transfer(self, request, pk=None):
        """Transfer org ownership to another member (admin-only)."""
        org = self.get_object()
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        to_user_id = (request.data or {}).get('user_id')
        if not to_user_id:
            return Response({'error': 'user_id_required'}, status=400)
        try:
            target = get_user_model().objects.get(id=int(to_user_id))
        except Exception:
            return Response({'error': 'user_not_found'}, status=404)
        # Pro target cannot admin more than one org
        tier, _ = get_subscription_for_scope(target, None)
        if tier == 'pro' and Organization.objects.filter(admin=target).exclude(id=org.id).exists():
            return Response({'error': 'pro_admin_single_org_limit'}, status=402)
        # Ensure target is at least a member
        OrgUser.objects.get_or_create(org=org, user=target, defaults={'role': 'admin'})
        org.admin_id = target.id
        org.save(update_fields=['admin_id'])  # post_save hook mirrors subscription
        return Response({'ok': True, 'admin_id': org.admin_id})

    @action(detail=True, methods=['get', 'post', 'delete'], url_path='members')
    def members(self, request, pk=None):
        org = self.get_object()
        if request.method == 'GET':
            qs = OrgUser.objects.filter(org=org).select_related('user').order_by('user_id')
            return Response(OrgUserSerializer(qs, many=True).data)
        # POST/DELETE require admin
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if request.method == 'POST':
            ser = OrgUserSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            user_id = ser.validated_data.get('user_id')
            email = ser.validated_data.get('email')
            role = ser.validated_data.get('role') or 'member'
            user_model = get_user_model()
            user = None
            if user_id is not None:
                try:
                    user = user_model.objects.get(id=int(user_id))
                except Exception:
                    return Response({'error': 'user_not_found_by_id'}, status=404)
            elif email:
                try:
                    user = user_model.objects.get(email=email)
                except Exception:
                    return Response({'error': 'user_not_found_by_email'}, status=404)
            else:
                return Response({'error': 'user_id_or_email_required'}, status=400)
            # Seat enforcement across all orgs owned by this admin
            allowed, details = can_admin_add_seat(request.user, user.id)
            if not allowed:
                return Response({'error': 'seats_exceeded', **details}, status=402)
            mu, _ = OrgUser.objects.update_or_create(org=org, user=user, defaults={'role': role or 'member'})
            return Response(OrgUserSerializer(mu).data, status=201)
        # DELETE: remove a member by user_id
        user_id = (request.data or {}).get('user_id')
        if not user_id:
            return Response({'error': 'user_id_required'}, status=400)
        if int(user_id) == org.admin_id:
            return Response({'error': 'cannot_remove_admin'}, status=400)
        deleted, _ = OrgUser.objects.filter(org=org, user_id=int(user_id)).delete()
        if not deleted:
            return Response({'error': 'not_found'}, status=404)
        return Response({'ok': True})

    @action(detail=True, methods=['get', 'post', 'delete'], url_path='invites')
    def invites(self, request, pk=None):
        org = self.get_object()
        if request.method == 'GET':
            qs = OrgInvite.objects.filter(org=org).order_by('-created_at')
            return Response(OrgInviteSerializer(qs, many=True).data)
        # POST/DELETE require admin
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if request.method == 'POST':
            email = (request.data or {}).get('email')
            role = (request.data or {}).get('role') or 'member'
            if not email:
                return Response({'error': 'email_required'}, status=400)
            # Rate limit: max ORG_INVITES_PER_HOUR per org per hour (default 20)
            try:
                max_per_hour = int(getattr(settings, 'ORG_INVITES_PER_HOUR', 20) or 0)
            except Exception:
                max_per_hour = 20
            if max_per_hour > 0:
                since = timezone.now() - timezone.timedelta(hours=1)
                count = OrgInvite.objects.filter(org=org, created_at__gte=since).count()
                if count >= max_per_hour:
                    return Response({'error': 'invite_rate_limited', 'retry_after_seconds': 3600}, status=429)
            # Soft seat check: warn if over capacity; acceptance is still hard-enforced
            seat_warn = None
            allowed, details = can_admin_add_seat(request.user, None)
            if not allowed:
                seat_warn = {'warning': 'seats_exceeded_on_accept', **details}
            # Reuse existing active invite if present; update role
            inv = OrgInvite.objects.filter(org=org, email=email, accepted_at__isnull=True, revoked_at__isnull=True).first()
            if inv:
                # If existing invite is expired, create a new one instead of reusing
                if not inv.is_active():
                    inv = None
            if inv:
                if inv.role != role:
                    inv.role = role
                    inv.save(update_fields=['role'])
            else:
                inv = OrgInvite.objects.create(org=org, email=email, role=role, invited_by=request.user)
            # Build accept URL to frontend (default /app?invite=TOKEN)
            base = getattr(settings, 'FRONTEND_INVITE_URL_BASE', None)
            if not base:
                base = request.build_absolute_uri('/app')
            sep = '&' if ('?' in base) else '?'
            accept_url = f'{base}{sep}invite={inv.token}'
            # Attempt to send email (best-effort)
            try:
                send_mail(
                    subject=f"You're invited to join {org.name} on Granterstellar",
                    message=(
                        f'Hello,\n\n'
                        f"You've been invited to join the organization '{org.name}' as {role}.\n\n"
                        f'Click to accept: {accept_url}\n\n'
                        f"If you don't recognize this, you can ignore this email."
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass
            data = OrgInviteSerializer(inv).data
            data['acceptance_url'] = accept_url
            if seat_warn:
                data['seats'] = seat_warn
            return Response(data, status=201)
        # DELETE: revoke by id
        invite_id = (request.data or {}).get('id')
        if not invite_id:
            return Response({'error': 'id_required'}, status=400)
        try:
            inv = OrgInvite.objects.get(id=int(invite_id), org=org)
        except OrgInvite.DoesNotExist:
            return Response({'error': 'not_found'}, status=404)
        if inv.accepted_at:
            return Response({'error': 'already_accepted'}, status=400)
        if inv.revoked_at:
            return Response({'error': 'already_revoked'}, status=400)
        inv.revoked_at = timezone.now()
        inv.save(update_fields=['revoked_at'])
        return Response({'ok': True})

    @action(detail=True, methods=['post'], url_path='allocation')
    def set_allocation(self, request, pk=None):
        """Enterprise-only: set this org's fixed monthly allocation for current month.
        Body: { allocation: int }
        """
        org = self.get_object()
        if org.admin_id != request.user.id:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        tier, _ = get_subscription_for_scope(request.user, None)
        if tier != 'enterprise':
            return Response({'error': 'not_enterprise'}, status=402)
        try:
            allocation = int((request.data or {}).get('allocation'))
            if allocation < 0:
                allocation = 0
        except Exception:
            return Response({'error': 'bad_allocation'}, status=400)
        month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        obj, _ = OrgProposalAllocation.objects.update_or_create(
            admin=request.user, org=org, month=month, defaults={'allocation': allocation}
        )
        return Response({'ok': True, 'allocation': obj.allocation})


class OrgInviteAcceptView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        token = (request.data or {}).get('token')
        if not token:
            return Response({'error': 'token_required'}, status=400)
        try:
            inv = OrgInvite.objects.select_related('org').get(token=token)
        except OrgInvite.DoesNotExist:
            return Response({'error': 'invalid_token'}, status=404)
        if inv.revoked_at:
            return Response({'error': 'invite_revoked'}, status=400)
        # If already accepted, report that explicitly before expiry logic
        if inv.accepted_at:
            return Response({'error': 'already_accepted'}, status=400)
        # Expiry check (only for not-yet-accepted invites)
        if not inv.is_active():
            return Response({'error': 'invite_expired'}, status=400)
        # Attach current user to org
        # Ensure the accepting user's email matches the invite
        if (request.user.email or '').strip().lower() != (inv.email or '').strip().lower():
            return Response({'error': 'email_mismatch', 'expected': inv.email, 'actual': request.user.email}, status=400)
        # Seat enforcement: check admin capacity before accepting
        admin_user = inv.org.admin
        allowed, details = can_admin_add_seat(admin_user, request.user.id)
        if not allowed:
            return Response({'error': 'seats_exceeded', **details}, status=402)
        OrgUser.objects.update_or_create(org=inv.org, user=request.user, defaults={'role': inv.role})
        inv.accepted_at = timezone.now()
        inv.save(update_fields=['accepted_at'])
        return Response({'ok': True, 'org_id': inv.org_id})
