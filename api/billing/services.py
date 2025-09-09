"""Billing service layer helpers.

Thin orchestration functions used by billing views. This isolates DB query
patterns and Stripe side-effects, making unit testing easier and views slimmer.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from .models import Subscription
from orgs.models import Organization

try:  # pragma: no cover - imported lazily in DEBUG often
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


def get_scope_subscription(user, org: Organization | None) -> Subscription | None:
    """Return most relevant subscription for a given scope (org or user)."""
    qs = Subscription.objects.all()
    if org is not None:
        qs = qs.filter(owner_org=org)
    else:
        qs = qs.filter(owner_user=user)
    sub = (
        qs.filter(status__in=['active', 'trialing']).order_by('-updated_at', '-id').first()  # type: ignore[arg-type]
        or qs.order_by('-updated_at', '-id').first()
    )
    return sub


def cancel_subscription(sub: Subscription, *, immediate: bool = False) -> tuple[bool, dict]:
    """Cancel a subscription.

    Returns (changed, info). When immediate=True and Stripe configured, attempts
    immediate deletion at provider; else sets cancel_at_period_end.
    """
    if immediate:
        if sub.status in ('canceled', 'incomplete_expired'):
            return False, {'reason': 'already_canceled'}
        if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
                stripe.Subscription.delete(sub.stripe_subscription_id)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                if not settings.DEBUG:
                    return False, {'error': 'stripe_error'}
        sub.status = 'canceled'
        sub.canceled_at = timezone.now()
        sub.cancel_at_period_end = False
        sub.save(update_fields=['status', 'canceled_at', 'cancel_at_period_end', 'updated_at'])
        return True, {'canceled': True, 'immediate': True}
    # Soft cancel at period end
    if sub.cancel_at_period_end:
        return False, {'reason': 'already_marked'}
    if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            if not settings.DEBUG:
                return False, {'error': 'stripe_error'}
    sub.cancel_at_period_end = True
    sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
    return True, {'cancel_at_period_end': True}


def resume_subscription(sub: Subscription) -> tuple[bool, dict]:
    """Clear cancel_at_period_end flag (and Stripe remote state if present)."""
    if not sub.cancel_at_period_end:
        return False, {'reason': 'not_marked'}
    if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=False)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            if not settings.DEBUG:
                return False, {'error': 'stripe_error'}
    sub.cancel_at_period_end = False
    sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
    return True, {'cancel_at_period_end': False}
