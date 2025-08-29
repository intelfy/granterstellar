from typing import Optional

from rest_framework import viewsets, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone

from billing.permissions import CanCreateProposal
from orgs.models import Organization
from .models import Proposal
from .serializers import ProposalSerializer
from billing.quota import can_unarchive
from orgs.models import OrgUser


class ProposalViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.all().order_by("-created_at")
    serializer_class = ProposalSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), CanCreateProposal()]
        # Read allowed for authenticated users for now; tighten as auth lands
        return [permissions.IsAuthenticated()] if not settings.DEBUG else [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not getattr(user, "is_authenticated", False):
            return qs.none()
        org: Optional[Organization] = None
        org_id = self.request.headers.get("X-Org-ID")
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        # Scope: personal (org is null, author=user) or org (org=org)
        if org:
            # Enforce membership at the application layer (in addition to DB RLS policies)
            is_member = OrgUser.objects.filter(org=org, user_id=user.id).exists()
            if not is_member:
                return qs.none()
            qs = qs.filter(org=org)
        else:
            qs = qs.filter(author=user, org__isnull=True)
        return qs

    def perform_create(self, serializer: ProposalSerializer):
        user = self.request.user
        org: Optional[Organization] = None
        org_id = self.request.headers.get("X-Org-ID")
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        # If org-scoped creation, require membership
        if org is not None:
            is_member = OrgUser.objects.filter(org=org, user_id=user.id).exists()
            if not is_member:
                # Fall back to personal scope when header is invalid
                org = None
        serializer.save(author=user, org=org)

    def partial_update(self, request: Request, *args, **kwargs):
        instance: Proposal = self.get_object()
        # Determine org scope from header
        org: Optional[Organization] = None
        org_id = request.headers.get("X-Org-ID")
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        # Ensure membership before allowing state changes in org scope
        if org is not None:
            is_member = OrgUser.objects.filter(org=org, user_id=request.user.id).exists()
            if not is_member:
                return Response({"error": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        requested_state = serializer.validated_data.get("state")

        if requested_state is not None:
            # Archiving allowed for all tiers (privacy); does not change usage cap status
            if requested_state == "archived" and instance.state != "archived":
                # set archived_at on transition to archived
                instance.archived_at = timezone.now()
            # Un-archiving should respect active caps only
            elif instance.state == "archived" and requested_state != "archived":
                allowed, details = can_unarchive(request.user, org, instance)
                if not allowed:
                    resp = Response({
                        "error": "quota_exceeded",
                        "reason": details.get("reason"),
                        "tier": details.get("tier"),
                        "limits": details.get("limits"),
                        "usage": details.get("usage"),
                    }, status=402)
                    resp["X-Quota-Reason"] = details.get("reason", "quota")
                    return resp

        # Clear archived_at if leaving archived state
        if instance.state == "archived" and requested_state and requested_state != "archived":
            instance.archived_at = None
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request: Request, *args, **kwargs):
        instance: Proposal = self.get_object()
        # For org-scoped delete (archive), ensure membership
        org: Optional[Organization] = None
        org_id = request.headers.get("X-Org-ID")
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        if org is not None:
            is_member = OrgUser.objects.filter(org=org, user_id=request.user.id).exists()
            if not is_member:
                return Response({"error": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        # Already archived → 204 idempotent
        if instance.state == "archived":
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Allow archive for all tiers (privacy)
        instance.state = "archived"
        instance.archived_at = timezone.now()
        update_fields = ["state", "archived_at"]
        if hasattr(instance, "updated_at"):
            update_fields.append("updated_at")
        instance.save(update_fields=update_fields)
        return Response(status=status.HTTP_204_NO_CONTENT)
