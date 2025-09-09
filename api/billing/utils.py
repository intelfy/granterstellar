from typing import Optional

from billing.models import Subscription
from orgs.models import Organization


def _personal_best_sub(user) -> Optional[Subscription]:
    qs = Subscription.objects.filter(owner_user=user)
    sub = qs.filter(status__in=['active', 'trialing']).order_by('-updated_at', '-id').first()
    if not sub:
        sub = qs.order_by('-updated_at', '-id').first()
    return sub


def upsert_org_subscription_from_admin(org: Organization) -> Subscription:
    """Mirror the admin user's subscription onto an org-owned Subscription row.

    If admin has no subscription or not active/trialing, set org to free/inactive.
    """
    admin = org.admin
    admin_sub = _personal_best_sub(admin)

    org_sub = Subscription.objects.filter(owner_org=org).order_by('-updated_at', '-id').first()
    if not org_sub:
        org_sub = Subscription(owner_org=org)

    if admin_sub and admin_sub.status in ('active', 'trialing'):
        org_sub.tier = admin_sub.tier
        org_sub.status = admin_sub.status
        org_sub.current_period_end = admin_sub.current_period_end
        org_sub.cancel_at_period_end = admin_sub.cancel_at_period_end
        # Mirror seats for visibility (enforcement reads from admin user subs)
        try:
            org_sub.seats = getattr(admin_sub, 'seats', 0) or 0
        except Exception:
            pass
    else:
        org_sub.tier = 'free'
        # status 'inactive' conveys no active subscription
        org_sub.status = 'inactive'
        org_sub.current_period_end = None
        org_sub.cancel_at_period_end = False
    org_sub.save()
    return org_sub


def get_admin_seat_capacity(admin) -> int:
    """Total paid seats for an admin across active/trialing personal subscriptions.
    If none, default to 1 seat so the admin can exist alone.
    """
    qs = Subscription.objects.filter(owner_user=admin, status__in=['active', 'trialing']).order_by('-updated_at', '-id')
    total = 0
    for s in qs:
        seats = getattr(s, 'seats', 0) or 0
        total += max(0, int(seats))
    return total if total > 0 else 1


def get_admin_seat_usage(admin) -> int:
    """Unique users across all organizations where this user is the admin."""
    from orgs.models import OrgUser  # local import to avoid cycles

    org_ids = list(Organization.objects.filter(admin=admin).values_list('id', flat=True))
    if not org_ids:
        return 0
    user_ids = set(OrgUser.objects.filter(org_id__in=org_ids).values_list('user_id', flat=True))
    return len(user_ids)


def can_admin_add_seat(admin, prospective_user_id: Optional[int] = None) -> tuple[bool, dict]:
    """Check if adding a user would exceed seat capacity across all admin orgs.
    If the user is already counted in any admin-owned org, adding them again doesn't use a new seat.
    Returns (allowed, details).
    """
    from orgs.models import OrgUser  # local import to avoid cycles

    capacity = get_admin_seat_capacity(admin)
    # Current unique usage
    org_ids = list(Organization.objects.filter(admin=admin).values_list('id', flat=True))
    current_users = set(OrgUser.objects.filter(org_id__in=org_ids).values_list('user_id', flat=True)) if org_ids else set()
    will_increase = False
    if prospective_user_id is not None and prospective_user_id not in current_users:
        will_increase = True
    usage = len(current_users) + (1 if will_increase else 0)
    if usage > capacity:
        return False, {'reason': 'seats_cap_reached', 'capacity': capacity, 'usage': len(current_users)}
    return True, {'capacity': capacity, 'usage': len(current_users)}
