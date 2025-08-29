from django.db import connection
from orgs.models import Organization, OrgUser


class RLSSessionMiddleware:
    """
    Sets Postgres session variables for RLS per request.
    - current_user_id
    - current_org_id (optional: header X-Org-ID)
    - current_role (derived from auth or header override when allowed)
    Safe no-op for non-Postgres backends.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = getattr(request.user, 'id', None)
        org_id = request.headers.get('X-Org-ID') or None
        role = 'admin' if getattr(request.user, 'is_staff', False) else 'user'
        # Validate org_id: only set if the current user is a member/admin of the org
        if org_id and str(org_id).isdigit() and user_id:
            try:
                org = Organization.objects.filter(id=int(org_id)).first()
                if org is None:
                    org_id = None
                else:
                    is_member = OrgUser.objects.filter(org=org, user_id=user_id).exists()
                    if not is_member:
                        org_id = None
            except Exception:
                org_id = None
        try:
            if connection.vendor == 'postgresql':
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT set_config('app.current_user_id', %s, false)",
                        [str(user_id) if user_id else ''],
                    )
                    cur.execute(
                        "SELECT set_config('app.current_org_id', %s, false)",
                        [str(org_id) if org_id else ''],
                    )
                    cur.execute(
                        "SELECT set_config('app.current_role', %s, false)",
                        [role],
                    )
        except Exception:
            # Avoid breaking requests if DB is not ready or not Postgres
            pass
        return self.get_response(request)
