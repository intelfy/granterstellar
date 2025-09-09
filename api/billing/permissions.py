from typing import Optional

from rest_framework.permissions import BasePermission

from orgs.models import Organization
from .quota import check_can_create_proposal


class CanCreateProposal(BasePermission):
    message = 'Creation quota exceeded. You can still edit existing proposals. Upgrade or archive to create new.'

    def has_permission(self, request, view) -> bool:
        # Infer org from header (kept in sync with RLS middleware)
        org: Optional[Organization] = None
        org_id = request.headers.get('X-Org-ID')
        if org_id and org_id.isdigit():
            try:
                org = Organization.objects.filter(id=int(org_id)).first()
            except Exception:
                org = None
        allowed, _details = check_can_create_proposal(request.user, org)
        if not allowed:
            self.message = _details.get('reason', self.message)
        return allowed
