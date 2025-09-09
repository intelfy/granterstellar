from typing import Optional

from rest_framework import viewsets, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone

from billing.permissions import CanCreateProposal
from orgs.models import Organization, OrgUser
from .models import Proposal
from .serializers import ProposalSerializer
from ai.section_pipeline import promote_section, get_section
from ai.models import AIMetric
from rest_framework.views import APIView
from billing.quota import can_unarchive


class ProposalViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.all().order_by('-created_at')
    serializer_class = ProposalSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), CanCreateProposal()]
        # Read allowed for authenticated users for now; tighten as auth lands
        return [permissions.IsAuthenticated()] if not settings.DEBUG else [permissions.AllowAny()]

    def get_queryset(self):
        """Return proposals scoped to either a specific org (X-Org-ID) or all
        organizations the user belongs to (admin or member).

        Previous logic attempted to support personal proposals with org=NULL.
        The schema has since evolved to enforce org NOT NULL (RLS + policies),
        so we expose a *personal organization* concept instead. Any legacy
        references to org NULL are removed in favor of auto-provisioning a
        personal org on first proposal creation (see perform_create).
        """
        qs = super().get_queryset()
        user = self.request.user
        if not getattr(user, 'is_authenticated', False):
            return qs.none()
        # Aggregate org ids where user is admin or member
        admin_org_ids = Organization.objects.filter(admin=user).values_list('id', flat=True)
        member_org_ids = OrgUser.objects.filter(user_id=user.id).values_list('org_id', flat=True)
        allowed_org_ids = set(admin_org_ids) | set(member_org_ids)
        org_id_header = self.request.headers.get('X-Org-ID')
        if org_id_header and org_id_header.isdigit():
            oid = int(org_id_header)
            if oid in allowed_org_ids:
                return qs.filter(org_id=oid)
            return qs.none()
        # No explicit org header: return all proposals from allowed orgs
        return qs.filter(org_id__in=allowed_org_ids)

    def perform_create(self, serializer: ProposalSerializer):
        """Create a proposal ensuring an org is always attached.

        Behavior:
          - If X-Org-ID provided and user is a member/admin → use that org.
          - Else: use (or create) a per-user personal org (admin = user).
            A membership row is also ensured for consistency with queries.
        """
        user = self.request.user
        org: Optional[Organization] = None
        org_id = self.request.headers.get('X-Org-ID')
        if org_id and org_id.isdigit():
            candidate = Organization.objects.filter(id=int(org_id)).first()
            # Use getattr to avoid static type checker complaints; admin_id always present at runtime.
            if candidate and (
                getattr(candidate, 'admin_id', None) == getattr(user, 'id', None)
                or OrgUser.objects.filter(
                    org=candidate,
                    user_id=getattr(user, 'id', None),
                ).exists()
            ):
                org = candidate
        if org is None:
            # Personal org provisioning path
            org = Organization.objects.filter(admin=user).order_by('id').first()
            if org is None:
                org = Organization.objects.create(name=f'{user.username}-personal', admin=user)
            # Ensure membership record (idempotent)
            OrgUser.objects.get_or_create(org=org, user=user, defaults={'role': 'admin'})
        serializer.save(author=user, org=org)

    def partial_update(self, request: Request, *args, **kwargs):
        instance: Proposal = self.get_object()
        # Determine org scope from header
        org: Optional[Organization] = None
        org_id = request.headers.get('X-Org-ID')
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        # Ensure membership before allowing state changes in org scope
        if org is not None:
            is_member = OrgUser.objects.filter(org=org, user_id=request.user.id).exists()
            if not is_member:
                return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        requested_state = serializer.validated_data.get('state')

        if requested_state is not None:
            # Archiving allowed for all tiers (privacy); does not change usage cap status
            if requested_state == 'archived' and instance.state != 'archived':
                # set archived_at on transition to archived
                instance.archived_at = timezone.now()
            # Un-archiving should respect active caps only
            elif instance.state == 'archived' and requested_state != 'archived':
                allowed, details = can_unarchive(request.user, org, instance)
                if not allowed:
                    resp = Response(
                        {
                            'error': 'quota_exceeded',
                            'reason': details.get('reason'),
                            'tier': details.get('tier'),
                            'limits': details.get('limits'),
                            'usage': details.get('usage'),
                        },
                        status=402,
                    )
                    resp['X-Quota-Reason'] = details.get('reason', 'quota')
                    return resp

        # Clear archived_at if leaving archived state
        if instance.state == 'archived' and requested_state and requested_state != 'archived':
            instance.archived_at = None
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request: Request, *args, **kwargs):
        instance: Proposal = self.get_object()
        # For org-scoped delete (archive), ensure membership
        org: Optional[Organization] = None
        org_id = request.headers.get('X-Org-ID')
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        if org is not None:
            is_member = OrgUser.objects.filter(org=org, user_id=request.user.id).exists()
            if not is_member:
                return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        # Already archived → 204 idempotent
        if instance.state == 'archived':
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Allow archive for all tiers (privacy)
        instance.state = 'archived'
        instance.archived_at = timezone.now()
        update_fields = ['state', 'archived_at']
        if hasattr(instance, 'updated_at'):
            update_fields.append('updated_at')
        instance.save(update_fields=update_fields)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SectionPromotionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, section_id: str):  # promote
        section = get_section(section_id)
        if not section:
            return Response({'error': 'not_found'}, status=404)
        # Simple ownership/membership enforcement mirroring Proposal scoping
        user = request.user
        proposal = section.proposal
        org_id_val = getattr(proposal, 'org_id', None)
        if org_id_val:
            is_member = OrgUser.objects.filter(org_id=org_id_val, user_id=user.id).exists()
            if not is_member:
                return Response({'error': 'forbidden'}, status=403)
        else:
            if getattr(proposal, 'author_id', None) != user.id:
                return Response({'error': 'forbidden'}, status=403)
        if section.locked:
            return Response({'error': 'already_locked'}, status=409)
        promote_section(section)
        # Record promotion metric (lightweight observability of lifecycle transitions)
        try:  # best-effort; failures shouldn't block response
            AIMetric.objects.create(  # type: ignore[arg-type]
                type='promote',
                model_id='lifecycle',
                proposal_id=getattr(section.proposal, 'id', None),
                section_id=str(getattr(section, 'id', '')),
                duration_ms=0,
                tokens_used=0,
                success=True,
                created_by=request.user if getattr(request.user, 'is_authenticated', False) else None,
                org_id=str(getattr(section.proposal, 'org_id', '') or ''),
            )
        except Exception:  # pragma: no cover - defensive
            pass
        return Response({'status': 'promoted', 'section_id': section_id})

    def delete(self, request: Request, section_id: str):  # unlock
        section = get_section(section_id)
        if not section:
            return Response(status=404)
        user = request.user
        proposal = section.proposal
        org_id_val = getattr(proposal, 'org_id', None)
        if org_id_val:
            is_member = OrgUser.objects.filter(org_id=org_id_val, user_id=user.id).exists()
            if not is_member:
                return Response({'error': 'forbidden'}, status=403)
        else:
            if getattr(proposal, 'author_id', None) != user.id:
                return Response({'error': 'forbidden'}, status=403)
        section.locked = False
        section.save(update_fields=['locked', 'updated_at'])
        return Response({'status': 'unlocked', 'section_id': section_id})
