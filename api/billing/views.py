from typing import Optional

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
 

from orgs.models import Organization
from .quota import (
    check_can_create_proposal,
    get_limits_for_tier,
    get_subscription_for_scope,
    get_usage,
    can_unarchive,
    get_extra_credits,
    compute_enterprise_effective_cap,
    get_effective_pro_monthly_cap,
)
from proposals.models import Proposal
from .models import Subscription
from .utils import get_admin_seat_capacity, get_admin_seat_usage
from orgs.allocation import compute_enterprise_allocations
from orgs.models import OrgProposalAllocation
from django.utils import timezone

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


@api_view(["GET"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def usage(request):
    # If unauthenticated (in DEBUG we allow), return safe defaults rather than erroring
    if not getattr(request.user, "is_authenticated", False):
        free_limits = get_limits_for_tier("free")
        return Response({
            "tier": "free",
            "status": "inactive",
            "limits": {"active_cap": free_limits.active_cap, "monthly_cap": free_limits.monthly_cap},
            "usage": {"active": 0, "created_this_period": 0},
            "can_create_proposal": False,
            "reason": "unauthenticated",
            "subscription": {"cancel_at_period_end": False, "current_period_end": None},
            "can_archive": True,
            "can_unarchive": True,
        })

    org: Optional[Organization] = None
    org_id = request.headers.get("X-Org-ID")
    if org_id and org_id.isdigit():
        try:
            org = Organization.objects.filter(id=int(org_id)).first()
        except Exception:
            org = None

    tier, status = get_subscription_for_scope(request.user, org)
    # Also surface lifecycle details for the selected scope
    sub_qs = Subscription.objects.all()
    if org is not None:
        sub_qs = sub_qs.filter(owner_org=org)
    else:
        sub_qs = sub_qs.filter(owner_user=request.user)
    sub = (
        sub_qs.filter(status__in=["active", "trialing"]).order_by("-updated_at", "-id").first()  # type: ignore[arg-type]
        or sub_qs.order_by("-updated_at", "-id").first()
    )
    limits = get_limits_for_tier(tier)
    usage = get_usage(request.user, org)
    allowed, details = check_can_create_proposal(request.user, org)

    # Archive/unarchive hints for UI
    # can_archive: always allowed per current policy
    can_archive = True
    # can_unarchive: evaluate against active cap by simulating unarchiving one archived proposal
    can_unarchive_flag = True
    try:
        dummy = Proposal(id=0, author=request.user, org=org, state='archived')  # not saved
        allowed_unarchive, _det = can_unarchive(request.user, org, dummy)
        can_unarchive_flag = bool(allowed_unarchive)
    except Exception:
        pass

    extras = get_extra_credits(request.user, org)
    # For pro tier, compute seat-based dynamic cap preview for UI
    effective_monthly_cap = limits.monthly_cap
    if tier == 'pro':
        effective_monthly_cap = get_effective_pro_monthly_cap(request.user, org)
    resp = {
        "tier": tier,
        "status": status,
    "limits": {"active_cap": limits.active_cap, "monthly_cap": effective_monthly_cap, "extras": extras},
        "usage": {"active": usage.active_count, "created_this_period": usage.created_this_period},
        "can_create_proposal": allowed,
        "reason": details.get("reason", "ok"),
        "subscription": {
            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)) if sub else False,
            "current_period_end": getattr(sub, "current_period_end", None).isoformat() if getattr(sub, "current_period_end", None) else None,
            "discount": getattr(sub, "discount", None) if sub else None,
        },
        "seats": {
            "capacity": get_admin_seat_capacity(request.user),
            "usage": get_admin_seat_usage(request.user),
        },
        "can_archive": can_archive,
        "can_unarchive": can_unarchive_flag,
    }
    # Enterprise allocation detail (only for admins; surfaces current month per-org allocation plan)
    if tier == 'enterprise':
        # Use date for month filter to match OrgProposalAllocation.month DateField
        start_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        admin_org_ids = list(Organization.objects.filter(admin=request.user).values_list('id', flat=True))
        fixed_map = {oa.org_id: oa.allocation for oa in OrgProposalAllocation.objects.filter(admin=request.user, month=start_month)}
        total_monthly = limits.monthly_cap or 0
        alloc = compute_enterprise_allocations(total_monthly, admin_org_ids, fixed_map)
        resp["enterprise_allocation"] = {
            "total": alloc.total,
            "orgs": {
                str(oid): {
                    "fixed": alloc.fixed.get(oid, 0),
                    "share": alloc.proportional.get(oid, 0),
                    "effective": alloc.fixed.get(oid, 0) + alloc.proportional.get(oid, 0),
                } for oid in admin_org_ids
            }
        }
        resp["enterprise_effective_caps"] = {str(k): v for k, v in compute_enterprise_effective_cap(request.user).items()}
    return Response(resp)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_portal(request):
    """
    Returns a Stripe customer portal URL for the current user's subscription.
    In DEBUG without Stripe configured, returns a placeholder URL.
    """
    # Find most recent subscription for user scope
    subs = Subscription.objects.filter(owner_user=request.user).order_by('-updated_at')
    sub = subs.first()
    customer_id = sub.stripe_customer_id if sub else ''
    return_url = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/') or 'http://localhost:8000'
    return_url = f"{return_url}/app#/billing"

    if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and customer_id:
        stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
        try:
            session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)  # type: ignore[attr-defined]
            url = session.get('url') if isinstance(session, dict) else getattr(session, 'url', None)
            if url:
                return Response({"url": url})
        except Exception:
            pass

    # Fallback in DEBUG or when missing configuration/customer
    if settings.DEBUG:
        return Response({"url": f"{return_url}?debug-portal=1"})
    return Response({"error": "portal_unavailable"}, status=503)


@api_view(["POST"])  # minimal checkout initializer
@permission_classes([IsAuthenticated])
def checkout(request):
    """
    Creates a Stripe Checkout Session for the current user or org scope.
    DEBUG fallback: returns a placeholder URL.
    Clients should pass optional JSON: { price_id?, mode?, org_id? }
    """
    price_id = (request.data or {}).get("price_id") or getattr(settings, "PRICE_PRO_MONTHLY", "")
    mode = (request.data or {}).get("mode") or "subscription"
    org_id = (request.data or {}).get("org_id")
    coupon = (request.data or {}).get("coupon")
    quantity = int((request.data or {}).get("quantity") or 1)
    if quantity < 1:
        quantity = 1

    # Determine scope and attach metadata for webhook resolution
    metadata = {"tier": "pro"}
    owner_user = request.user
    owner_org = None
    if org_id:
        try:
            owner_org = Organization.objects.filter(id=int(org_id)).first()
        except Exception:
            owner_org = None
    if owner_org is not None:
        metadata["org_id"] = str(owner_org.id)
    else:
        metadata["user_id"] = str(owner_user.id)
    if coupon:
        metadata["coupon_code"] = str(coupon)
    # Mirror seats in metadata so webhooks can infer quantity
    metadata["seats"] = str(quantity)

    # If a bundle price is used and mode not explicitly set, switch to one-time payment
    def _is_bundle(pid: str) -> bool:
        return pid in {
            (getattr(settings, 'PRICE_BUNDLE_1', '') or '').strip(),
            (getattr(settings, 'PRICE_BUNDLE_10', '') or '').strip(),
            (getattr(settings, 'PRICE_BUNDLE_25', '') or '').strip(),
        }
    if (request.data or {}).get("mode") is None and _is_bundle(price_id):
        mode = 'payment'
        # Annotate bundle size for debugging/analytics (webhook relies on price id, not this flag)
        if price_id == (getattr(settings, 'PRICE_BUNDLE_1', '') or '').strip():
            metadata['bundle'] = '1'
        elif price_id == (getattr(settings, 'PRICE_BUNDLE_10', '') or '').strip():
            metadata['bundle'] = '10'
        elif price_id == (getattr(settings, 'PRICE_BUNDLE_25', '') or '').strip():
            metadata['bundle'] = '25'

    success_url = (getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/') or 'http://localhost:8000') + "/app#/billing?success=1"
    cancel_url = (getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/') or 'http://localhost:8000') + "/app#/billing?canceled=1"

    if not stripe or not getattr(settings, 'STRIPE_SECRET_KEY', '').strip() or not price_id:
        if settings.DEBUG:
            # Return a fake URL for UI wiring
            return Response({"url": f"{success_url}&debug-checkout=1"})
        return Response({"error": "checkout_unavailable"}, status=503)

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
        params = dict(
            mode=mode,
            line_items=[{"price": price_id, "quantity": quantity}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=f"user:{owner_user.id}",
            metadata=metadata,
        )
        # Attach coupon/promotion code when provided and valid
        if coupon:
            try:
                # Try promotion code lookup first (recommended)
                promo_list = stripe.PromotionCode.list(code=coupon, active=True)  # type: ignore[attr-defined]
                promo = promo_list.data[0] if getattr(promo_list, 'data', []) else None
                if promo:
                    params["discounts"] = [{"promotion_code": promo.id}]
                else:
                    # Fallback to coupon id if a raw coupon identifier is provided
                    c = stripe.Coupon.retrieve(coupon)  # type: ignore[attr-defined]
                    if c and getattr(c, 'valid', False):
                        params["discounts"] = [{"coupon": c.id}]
            except Exception:
                # Ignore invalid coupon in production (no discount applied); in DEBUG we still proceed
                pass
        session = stripe.checkout.Session.create(**params)  # type: ignore[attr-defined]
        url = session.get('url') if isinstance(session, dict) else getattr(session, 'url', None)
        if not url:
            return Response({"error": "no_url"}, status=500)
        return Response({"url": url})
    except Exception:
        if settings.DEBUG:
            return Response({"url": f"{success_url}&debug-checkout=1"})
        return Response({"error": "checkout_failed"}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    """Marks the current subscription to cancel at period end (user or org scope).
    Optional immediate cancel when body contains { "immediate": true }.
    """
    org_id = (request.data or {}).get("org_id")
    sub_qs = Subscription.objects.all()
    if org_id:
        try:
            org = Organization.objects.filter(id=int(org_id)).first()
        except Exception:
            org = None
        if not org:
            return Response({"error": "org_not_found"}, status=404)
        if org.admin_id != request.user.id:
            return Response({"error": "forbidden"}, status=403)
        sub_qs = sub_qs.filter(owner_org=org)
    else:
        sub_qs = sub_qs.filter(owner_user=request.user)
    sub = sub_qs.order_by('-updated_at').first()
    if not sub:
        return Response({"error": "not_subscribed"}, status=404)
    immediate = bool((request.data or {}).get("immediate"))
    if immediate:
        # Attempt immediate cancel in Stripe when configured
        if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
                stripe.Subscription.delete(sub.stripe_subscription_id)  # type: ignore[attr-defined]
            except Exception:
                if not settings.DEBUG:
                    return Response({"error": "stripe_error"}, status=502)
        # Mark locally as canceled now
        sub.status = 'canceled'
        sub.canceled_at = timezone.now()
        sub.cancel_at_period_end = False
        sub.save(update_fields=['status', 'canceled_at', 'cancel_at_period_end', 'updated_at'])
        # Cascade: if a personal subscription was canceled, mirror org subscriptions for admin to free/inactive
        if sub.owner_user_id:
            try:
                from billing.utils import upsert_org_subscription_from_admin
                for org in Organization.objects.filter(admin=sub.owner_user).iterator():
                    upsert_org_subscription_from_admin(org)
            except Exception:
                pass
        return Response({"ok": True, "canceled": True, "cancel_at_period_end": False})
    # If Stripe configured, attempt to set cancel_at_period_end
    if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)  # type: ignore[attr-defined]
        except Exception:
            if not settings.DEBUG:
                return Response({"error": "stripe_error"}, status=502)
    sub.cancel_at_period_end = True
    sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
    return Response({"ok": True, "cancel_at_period_end": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_subscription(request):
    """Clears cancel_at_period_end for the current subscription (user or org scope)."""
    org_id = (request.data or {}).get("org_id")
    sub_qs = Subscription.objects.all()
    if org_id:
        try:
            org = Organization.objects.filter(id=int(org_id)).first()
        except Exception:
            org = None
        if not org:
            return Response({"error": "org_not_found"}, status=404)
        if org.admin_id != request.user.id:
            return Response({"error": "forbidden"}, status=403)
        sub_qs = sub_qs.filter(owner_org=org)
    else:
        sub_qs = sub_qs.filter(owner_user=request.user)
    sub = sub_qs.order_by('-updated_at').first()
    if not sub:
        return Response({"error": "not_subscribed"}, status=404)
    if stripe and getattr(settings, 'STRIPE_SECRET_KEY', '').strip() and sub.stripe_subscription_id:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=False)  # type: ignore[attr-defined]
        except Exception:
            if not settings.DEBUG:
                return Response({"error": "stripe_error"}, status=502)
    sub.cancel_at_period_end = False
    sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
    return Response({"ok": True, "cancel_at_period_end": False})
