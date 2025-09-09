from dataclasses import dataclass
from typing import Optional, Tuple

from django.conf import settings
from django.utils import timezone
from django.db import models

from billing.models import Subscription, ExtraCredits
from orgs.models import Organization, OrgProposalAllocation
from proposals.models import Proposal


@dataclass
class QuotaLimits:
    active_cap: Optional[int] = None
    monthly_cap: Optional[int] = None


@dataclass
class QuotaUsage:
    active_count: int
    created_this_period: int


def _period_start() -> timezone.datetime:
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def get_subscription_for_scope(user, org: Optional[Organization]) -> Tuple[str, str]:
    """
    Returns (tier, status). Defaults to ("free", "inactive") when none active.
    Prefers active/trialing subscription for the org scope; else user scope.
    """
    qs = Subscription.objects.all()
    if org is not None:
        qs = qs.filter(owner_org=org)
    else:
        qs = qs.filter(owner_user=user)
    # Prefer active/trialing
    sub = (
        qs.filter(status__in=["active", "trialing"])  # type: ignore[arg-type]
        .order_by("-updated_at", "-id")
        .first()
    )
    if not sub:
        # fallback to most recent any status
        sub = qs.order_by("-updated_at", "-id").first()
    if not sub:
        return "free", "inactive"
    # Treat canceled/incomplete as free; allow a configurable grace window for past_due
    if sub.status in ("active", "trialing"):
        return sub.tier, sub.status
    if sub.status == "past_due":
        # Grace window in days (default 3). Uses updated_at as the start of past_due.
        try:
            grace_days = int(getattr(settings, "FAILED_PAYMENT_GRACE_DAYS", 3) or 0)
        except Exception:
            grace_days = 0
        if grace_days > 0 and getattr(sub, "updated_at", None):
            try:
                delta = timezone.now() - sub.updated_at
                if delta.days < grace_days:
                    return sub.tier, sub.status
            except Exception:
                pass
        return "free", sub.status
    # All other non-active statuses behave as free
    return "free", sub.status


def get_subscription_obj_for_scope(user, org: Optional[Organization]) -> Optional[Subscription]:
    """Returns the most relevant Subscription object for the given scope (active/trialing preferred).
    Falls back to the most recent subscription if none active.
    """
    qs = Subscription.objects.all()
    if org is not None:
        qs = qs.filter(owner_org=org)
    else:
        qs = qs.filter(owner_user=user)
    sub = (
        qs.filter(status__in=["active", "trialing"])  # type: ignore[arg-type]
        .order_by("-updated_at", "-id")
        .first()
    )
    if not sub:
        sub = qs.order_by("-updated_at", "-id").first()
    return sub


def get_limits_for_tier(tier: str) -> QuotaLimits:
    t = tier.lower()
    if t == "free":
        return QuotaLimits(active_cap=getattr(settings, "QUOTA_FREE_ACTIVE_CAP", 1), monthly_cap=None)
    if t == "pro":
        return QuotaLimits(active_cap=None, monthly_cap=getattr(settings, "QUOTA_PRO_MONTHLY_CAP", 20))
    if t == "enterprise":
        cap = getattr(settings, "QUOTA_ENTERPRISE_MONTHLY_CAP", None)
        return QuotaLimits(active_cap=None, monthly_cap=cap)
    # Unknown tiers fall back to free
    return QuotaLimits(active_cap=getattr(settings, "QUOTA_FREE_ACTIVE_CAP", 1), monthly_cap=None)


def get_usage(user, org: Optional[Organization]) -> QuotaUsage:
    """Return usage for the provided scope.

    Legacy behavior counted personal proposals via org IS NULL. Schema now enforces
    NOT NULL; we treat a missing org argument as zero usage (caller will typically
    supply an org). This keeps quota logic backwards compatible during transition.
    """
    period_start = _period_start()
    if org is None:
        return QuotaUsage(active_count=0, created_this_period=0)
    base = Proposal.objects.filter(org=org)
    active_count = base.exclude(state="archived").count()
    created_this_period = base.filter(created_at__gte=period_start).count()
    return QuotaUsage(active_count=active_count, created_this_period=created_this_period)


def _month_start() -> timezone.datetime:
    return timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def get_extra_credits(user, org: Optional[Organization]) -> int:
    month = _month_start().date()
    qs = ExtraCredits.objects.all()
    if org is not None:
        qs = qs.filter(owner_org=org, month=month)
    else:
        qs = qs.filter(owner_user=user, month=month)
    total = qs.aggregate(total=models.Sum('proposals'))['total'] or 0  # type: ignore[attr-defined]
    return int(total)


def get_effective_pro_monthly_cap(user, org: Optional[Organization]) -> Optional[int]:
    """If a relevant subscription with seats exists, compute cap = seats * QUOTA_PRO_PER_SEAT + extras.
    Otherwise, fall back to static QUOTA_PRO_MONTHLY_CAP (possibly None).
    """
    static_cap = getattr(settings, "QUOTA_PRO_MONTHLY_CAP", 20)
    sub = get_subscription_obj_for_scope(user, org)
    # Only apply seat-based cap when we have an active/trialing sub with seats > 0
    if sub and sub.status in ("active", "trialing"):
        seats = int(getattr(sub, "seats", 0) or 0)
        if seats > 0:
            per_seat = int(getattr(settings, "QUOTA_PRO_PER_SEAT", 10) or 10)
            extras = get_extra_credits(user, org)
            return seats * per_seat + int(extras or 0)
    # Fallback to static (legacy) behavior; do not auto-add extras here since extras are applied in enforcement
    return static_cap


def compute_enterprise_effective_cap(admin_user) -> dict:
    """Returns {org_id:int -> effective_cap:int} for the admin across their orgs this month.
    Uses OrgProposalAllocation with QUOTA_ENTERPRISE_MONTHLY_CAP and splits remainder equally among zero allocations.
    """
    monthly_cap = getattr(settings, "QUOTA_ENTERPRISE_MONTHLY_CAP", None) or 0
    if monthly_cap <= 0:
        return {}
    month = _month_start().date()
    org_ids = list(Organization.objects.filter(admin=admin_user).values_list('id', flat=True))
    fixed = {
        row.org_id: max(0, int(row.allocation))
        for row in OrgProposalAllocation.objects.filter(admin=admin_user, month=month)
    }
    # Fill missing with 0
    fixed = {oid: fixed.get(oid, 0) for oid in org_ids}
    sum_fixed = sum(fixed.values())
    remaining = max(0, monthly_cap - sum_fixed)
    zeros = [oid for oid in org_ids if fixed.get(oid, 0) == 0]
    per_zero = (remaining // len(zeros)) if zeros else 0
    extra_first = (remaining % len(zeros)) if zeros else 0
    result = {}
    for idx, oid in enumerate(org_ids):
        share = 0
        if fixed.get(oid, 0) == 0 and zeros:
            share = per_zero + (1 if idx < extra_first else 0)
        result[oid] = fixed.get(oid, 0) + share
    return result


def check_can_create_proposal(user, org: Optional[Organization]):
    """
    Returns (allowed: bool, details: dict)
    details contains: tier, limits, usage, reason
    """
    tier, status = get_subscription_for_scope(user, org)
    limits = get_limits_for_tier(tier)
    usage = get_usage(user, org)

    # For free tier: lifetime cap of 1 proposal in the selected scope
    if tier == "free":
        total = Proposal.objects.filter(org=org).count() if org is not None else 0
        if total >= 1:
            return False, {
                "tier": tier,
                "status": status,
                "reason": "active_cap_reached",
                "limits": {"active_cap": limits.active_cap, "monthly_cap": limits.monthly_cap},
                "usage": {"active": usage.active_count, "created_this_period": usage.created_this_period},
            }

    # Active cap (free)
    if limits.active_cap is not None and usage.active_count >= limits.active_cap:
        return False, {
            "tier": tier,
            "status": status,
            "reason": "active_cap_reached",
            "limits": {"active_cap": limits.active_cap, "monthly_cap": limits.monthly_cap},
            "usage": {"active": usage.active_count, "created_this_period": usage.created_this_period},
        }

    # Monthly cap (pro/enterprise) with seat-based override for Pro
    effective_monthly_cap = limits.monthly_cap
    if tier == "pro":
        # Compute dynamic cap when subscription with seats exists; else use static
        effective_monthly_cap = get_effective_pro_monthly_cap(user, org)
    if effective_monthly_cap is not None and usage.created_this_period >= effective_monthly_cap:
        return False, {
            "tier": tier,
            "status": status,
            "reason": "monthly_cap_reached",
            "limits": {"active_cap": limits.active_cap, "monthly_cap": effective_monthly_cap},
            "usage": {"active": usage.active_count, "created_this_period": usage.created_this_period},
        }

    return True, {
        "tier": tier,
        "status": status,
        "reason": "ok",
        "limits": {"active_cap": limits.active_cap, "monthly_cap": effective_monthly_cap},
        "usage": {"active": usage.active_count, "created_this_period": usage.created_this_period},
    }


def can_unarchive(user, org: Optional[Organization], proposal: Proposal) -> Tuple[bool, dict]:
    """Checks whether changing state from archived to active would exceed active cap.
    Does not apply monthly caps (unarchive is not a creation)."""
    tier, status = get_subscription_for_scope(user, org)
    limits = get_limits_for_tier(tier)
    # Count actives excluding this proposal
    base = Proposal.objects.filter(org=org) if org is not None else Proposal.objects.none()
    active_others = base.exclude(state="archived").exclude(id=proposal.id).count()
    if limits.active_cap is not None and active_others >= limits.active_cap:
        return False, {
            "tier": tier,
            "status": status,
            "reason": "active_cap_reached",
            "limits": {"active_cap": limits.active_cap, "monthly_cap": limits.monthly_cap},
            "usage": {"active": active_others, "created_this_period": get_usage(user, org).created_this_period},
        }
    return True, {
        "tier": tier,
        "status": status,
        "reason": "ok",
        "limits": {"active_cap": limits.active_cap, "monthly_cap": limits.monthly_cap},
        "usage": {"active": active_others, "created_this_period": get_usage(user, org).created_this_period},
    }
