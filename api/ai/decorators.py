from functools import wraps
from typing import Callable, Optional
from django.conf import settings
from rest_framework.response import Response
from billing.quota import get_subscription_for_scope
from orgs.models import Organization

# NOTE: Reuses existing _rate_limit_check logic from views by importing lazily to avoid circulars.


def ai_protected(endpoint_type: str, plan_gate: bool = True):
    """Decorator consolidating plan gating + rate limiting for AI endpoints.

    Parameters:
      endpoint_type: one of 'plan','write','revise','format'
      plan_gate: whether to enforce paid tier (write/revise/format). 'plan' may pass plan_gate=False.

    Behavior:
      - Allows anonymous in DEBUG or AI_TEST_OPEN.
      - When plan_gate and not free tier required, blocks free users with 402.
      - Applies single-write guard (write only) & rate limiter.
    """

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            from django.core.cache import cache

            # Anonymous bypass in DEBUG/test-open
            if not (settings.DEBUG or getattr(settings, 'AI_TEST_OPEN', False)):
                user = getattr(request, 'user', None)
                if not getattr(user, 'is_authenticated', False):
                    return Response({'error': 'unauthorized'}, status=401)
                # Plan gating
                if plan_gate:
                    org: Optional[Organization] = None
                    org_id = request.META.get('HTTP_X_ORG_ID', '')
                    if org_id and str(org_id).isdigit():
                        try:
                            org = Organization.objects.filter(id=int(org_id)).first()
                        except Exception:
                            org = None
                    tier, _status = get_subscription_for_scope(user, org)
                    if tier == 'free':
                        resp = Response({'error': 'quota_exceeded', 'reason': 'ai_requires_pro'}, status=402)
                        resp['X-Quota-Reason'] = 'ai_requires_pro'
                        return resp
            # Single-write guard (write only)
            if endpoint_type == 'write':
                if (settings.DEBUG or getattr(settings, 'AI_ENFORCE_RATE_LIMIT_DEBUG', False)) and int(
                    getattr(settings, 'AI_RATE_PER_MIN_PRO', 20) or 20
                ) == 1:
                    uid = getattr(getattr(request, 'user', None), 'id', None)
                    if uid:
                        key_once = f'ai_dbg_single_write:{uid}'
                        if cache.get(key_once):
                            return Response({'error': 'rate_limited', 'retry_after': 60}, status=429)
                        cache.set(key_once, 1, 60)
            # Rate limiter (imports helper for reuse)
            from .views import _rate_limit_check  # type: ignore

            rl = _rate_limit_check(request, endpoint_type)
            if rl is not None:
                return rl
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
