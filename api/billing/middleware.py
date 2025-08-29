from typing import Optional

from django.http import JsonResponse

from orgs.models import Organization
from .quota import check_can_create_proposal


class QuotaEnforcementMiddleware:
    """
    Blocks proposal creation when over quota.
    For now, guards POST to /api/proposals (when we add that endpoint).
    Exposes X-Quota-Reason header and 402 status for clarity.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
    # Only enforce for creation of proposals. Edits (PATCH/PUT) are always allowed
    # so users can work on their single allowed draft without being blocked by quota.
        if request.method == "POST" and "/api/proposals" in request.path:
            # Skip if not authenticated yet; DRF will enforce auth and permission later
            user = getattr(request, "user", None)
            if not getattr(user, "is_authenticated", False):
                return self.get_response(request)
            org: Optional[Organization] = None
            org_id = request.headers.get("X-Org-ID")
            if org_id and org_id.isdigit():
                try:
                    org = Organization.objects.filter(id=int(org_id)).first()
                except Exception:
                    org = None
            allowed, details = check_can_create_proposal(request.user, org)
            if not allowed:
                data = {
                    "error": "quota_exceeded",
                    "reason": details.get("reason"),
                    "tier": details.get("tier"),
                    "limits": details.get("limits"),
                    "usage": details.get("usage"),
                }
                resp = JsonResponse(data, status=402)
                resp["X-Quota-Reason"] = details.get("reason", "quota")
                return resp
        return self.get_response(request)
