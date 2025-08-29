from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth import get_user_model
from orgs.models import Organization
from .models import Subscription, ExtraCredits
import json

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


@require_POST
@csrf_exempt  # Stripe sends cross-origin POSTs; CSRF token cannot be present.
# Compensating controls:
#  - Signature verification with STRIPE_WEBHOOK_SECRET in non-DEBUG
#  - POST-only; rejects unsigned in production; payload is parsed as JSON dict
def stripe_webhook(request):
    payload = request.body.decode('utf-8')
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    secret = (settings.STRIPE_WEBHOOK_SECRET or '').strip()

    event = None
    if stripe and secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except Exception:
            return HttpResponseBadRequest('invalid signature')
    else:
        # Allow unsigned events in DEBUG to ease local testing w/o Stripe account
        if not settings.DEBUG:
            return HttpResponseBadRequest('webhook not configured')
        try:
            event = json.loads(payload or '{}')
        except Exception:
            return HttpResponseBadRequest('invalid payload')

    def _as_dict(obj):
        if isinstance(obj, dict):
            return obj
        try:
            # Stripe object → dict
            return obj.to_dict()  # type: ignore[attr-defined]
        except Exception:
            return {}

    def _epoch_to_dt(epoch):
        try:
            return timezone.datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        except Exception:
            return None

    def _extract_qty_from_obj(data: dict) -> int | None:
        """Best-effort extraction of the seat quantity from various Stripe objects.
        Looks at:
        - metadata.seats or metadata.quantity
        - subscription.items.data[].quantity (prefers matching configured price ids)
        - invoice.lines.data[].quantity
        - checkout.session.line_items.data[].quantity (when expanded)
        Returns int or None if unknown.
        """
        try:
            metadata = data.get('metadata') or {}
            # 1) Explicit metadata hint
            for k in ('seats', 'quantity'):
                if k in metadata:
                    q = int(metadata.get(k) or 0)
                    if q >= 0:
                        return q
        except Exception:
            pass

        def _match_items(items_list):
            qty = None
            try:
                price_ids = {
                    (getattr(settings, 'PRICE_PRO_MONTHLY', '') or '').strip(),
                    (getattr(settings, 'PRICE_PRO_YEARLY', '') or '').strip(),
                }
                # Prefer the item whose price matches our configured price ids
                best = None
                for it in items_list:
                    price = (it.get('price') or {}) if isinstance(it.get('price'), dict) else {}
                    price_id = price.get('id') if isinstance(price, dict) else None
                    if price_id and price_id in price_ids:
                        best = it
                        break
                if not best and items_list:
                    best = items_list[0]
                if best is not None:
                    q = best.get('quantity')
                    if isinstance(q, int):
                        qty = q
            except Exception:
                qty = None
            return qty

        # 2) Subscription object with items
        try:
            if data.get('object') == 'subscription' or 'items' in data:
                items = (data.get('items') or {}).get('data') if isinstance(data.get('items'), dict) else None
                if items and isinstance(items, list):
                    q = _match_items(items)
                    if isinstance(q, int):
                        return q
        except Exception:
            pass

        # 3) Invoice lines
        try:
            if data.get('object') == 'invoice' or 'lines' in data:
                lines = (data.get('lines') or {}).get('data') if isinstance(data.get('lines'), dict) else None
                if lines and isinstance(lines, list):
                    q = _match_items(lines)
                    if isinstance(q, int):
                        return q
        except Exception:
            pass

        # 4) Checkout Session expanded line_items
        try:
            if data.get('object') == 'checkout.session' and 'line_items' in data:
                line_items = (data.get('line_items') or {}).get('data') if isinstance(data.get('line_items'), dict) else None
                if line_items and isinstance(line_items, list):
                    q = _match_items(line_items)
                    if isinstance(q, int):
                        return q
        except Exception:
            pass

        return None

    def _upsert_subscription_from_obj(obj_dict, fallback_tier: str = 'pro', status_override: str | None = None):
        data = obj_dict or {}
        metadata = data.get('metadata') or {}
        tier = (metadata.get('tier') or fallback_tier).lower()
        if tier not in ('free', 'pro', 'enterprise'):
            tier = fallback_tier

        # Identify owner from metadata
        owner_user = None
        owner_org = None
        User = get_user_model()
        if metadata.get('user_id'):
            try:
                owner_user = User.objects.filter(id=int(metadata['user_id'])).first()
            except Exception:
                owner_user = None
        if owner_user is None and metadata.get('org_id'):
            try:
                owner_org = Organization.objects.filter(id=int(metadata['org_id'])).first()
            except Exception:
                owner_org = None

        # If neither metadata present, try to infer from existing subscription by stripe ids
        cust_id = data.get('customer') or ''
        sub_id = data.get('id') or data.get('subscription') or ''
        status = status_override or data.get('status') or 'active'
        current_period_end = _epoch_to_dt(data.get('current_period_end'))
        cancel_at_period_end = bool(data.get('cancel_at_period_end')) if 'cancel_at_period_end' in data else None

        # Look up existing subscription by sub_id first
        sub_qs = Subscription.objects.all()
        sub = None
        if sub_id:
            sub = sub_qs.filter(stripe_subscription_id=sub_id).order_by('-updated_at').first()
        if not sub and cust_id:
            sub = sub_qs.filter(stripe_customer_id=cust_id).order_by('-updated_at').first()

        # Create when missing and we can resolve an owner
        if not sub:
            if not owner_user and not owner_org:
                # No way to attach owner; ignore silently (idempotent behavior)
                return
            sub = Subscription(owner_user=owner_user, owner_org=owner_org)

        # Helper: extract discount summary from Stripe-like object
        def _extract_discount(obj: dict):
            try:
                disc = obj.get('discount')
                discounts = obj.get('discounts')
                if not disc and isinstance(discounts, list) and len(discounts) > 0:
                    disc = discounts[0]
                if not isinstance(disc, dict):
                    # Some SDKs return Discount objects; fall back to dict conversion
                    disc = disc.to_dict() if hasattr(disc, 'to_dict') else None  # type: ignore[attr-defined]
                if not disc:
                    return None
                promo = disc.get('promotion_code')
                if isinstance(promo, dict):
                    promo = promo.get('id')
                coupon = disc.get('coupon')
                coupon_id = coupon.get('id') if isinstance(coupon, dict) else (coupon if isinstance(coupon, str) else None)
                coupon_obj = coupon if isinstance(coupon, dict) else {}
                res = {
                    'source': 'promotion_code' if promo else 'coupon',
                    'id': promo or coupon_id,
                    'percent_off': coupon_obj.get('percent_off'),
                    'amount_off': coupon_obj.get('amount_off') or 0,
                    'currency': coupon_obj.get('currency'),
                    'duration': coupon_obj.get('duration'),
                    'duration_in_months': coupon_obj.get('duration_in_months'),
                }
                if not res.get('id'):
                    return None
                return res
            except Exception:
                return None

        # Update fields
        if owner_user and not sub.owner_user and not sub.owner_org:
            sub.owner_user = owner_user
        if owner_org and not sub.owner_org and not sub.owner_user:
            sub.owner_org = owner_org  # type: ignore[assignment]
        if cust_id:
            sub.stripe_customer_id = cust_id
        if sub_id:
            sub.stripe_subscription_id = sub_id
        sub.tier = tier
        sub.status = status
        if current_period_end:
            sub.current_period_end = current_period_end
        if cancel_at_period_end is not None:
            sub.cancel_at_period_end = cancel_at_period_end
        # Seats/quantity detection (robust)
        qty = _extract_qty_from_obj(data)
        if isinstance(qty, int) and qty >= 0:
            sub.seats = qty
        disc_summary = _extract_discount(data)
        if disc_summary is not None:
            sub.discount = disc_summary  # type: ignore[assignment]
        sub.save()

    event_type = event.get('type', '') if isinstance(event, dict) else getattr(event, 'type', '')
    obj = _as_dict(event.get('data', {}).get('object')) if isinstance(event, dict) else {}

    def _bundle_amount_for_price_id(price_id: str) -> int:
        pid = (price_id or '').strip()
        if not pid:
            return 0
        if pid == (getattr(settings, 'PRICE_BUNDLE_1', '') or '').strip():
            return 1
        if pid == (getattr(settings, 'PRICE_BUNDLE_10', '') or '').strip():
            return 10
        if pid == (getattr(settings, 'PRICE_BUNDLE_25', '') or '').strip():
            return 25
        return 0

    def _credit_extras_from_invoice(inv: dict):
        # Detect bundle line items and add ExtraCredits for current month
        try:
            lines = (inv.get('lines') or {}).get('data') if isinstance(inv.get('lines'), dict) else None
            if not lines:
                return
            # Owner resolution: require metadata from invoice/session
            metadata = inv.get('metadata') or {}
            owner_user = None
            owner_org = None
            User = get_user_model()
            if metadata.get('user_id'):
                try:
                    owner_user = User.objects.filter(id=int(metadata['user_id'])).first()
                except Exception:
                    owner_user = None
            if owner_user is None and metadata.get('org_id'):
                try:
                    owner_org = Organization.objects.filter(id=int(metadata['org_id'])).first()
                except Exception:
                    owner_org = None
            if not owner_user and not owner_org:
                return
            total_extras = 0
            for li in lines:
                price = (li.get('price') or {}) if isinstance(li.get('price'), dict) else {}
                price_id = price.get('id') if isinstance(price, dict) else None
                qty = li.get('quantity') if isinstance(li.get('quantity'), int) else 1
                amount = _bundle_amount_for_price_id(price_id or '')
                if amount > 0:
                    total_extras += amount * max(1, int(qty))
            if total_extras > 0:
                month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
                if owner_org is not None:
                    obj, _ = ExtraCredits.objects.get_or_create(owner_org=owner_org, owner_user=None, month=month, defaults={'proposals': 0})
                else:
                    obj, _ = ExtraCredits.objects.get_or_create(owner_user=owner_user, owner_org=None, month=month, defaults={'proposals': 0})
                obj.proposals = int(obj.proposals or 0) + int(total_extras)
                obj.save(update_fields=['proposals'])
        except Exception:
            # Best-effort; ignore bundle credits on errors
            pass

    if event_type == 'checkout.session.completed':
        # Session includes customer, subscription, metadata
        _upsert_subscription_from_obj(obj, fallback_tier='pro', status_override='active')
        # Optionally log coupon_code in metadata (no DB schema here; can extend later)
    elif event_type in {'customer.subscription.updated', 'customer.subscription.created'}:
        _upsert_subscription_from_obj(obj)
    elif event_type in {'invoice.paid', 'invoice.payment_succeeded'}:
        # Capture seats and discount from invoices too (in case subscription item quantity/coupon changes)
        _upsert_subscription_from_obj(obj)
        try:
            sub_id = obj.get('subscription')
            if sub_id:
                disc = obj.get('discount') or {}
                # Normalize discount structure similar to _extract_discount
                coupon = disc.get('coupon') if isinstance(disc, dict) else None
                coupon_obj = coupon if isinstance(coupon, dict) else {}
                promo = disc.get('promotion_code') if isinstance(disc, dict) else None
                if isinstance(promo, dict):
                    promo = promo.get('id')
                coupon_id = coupon_obj.get('id') if isinstance(coupon_obj, dict) else (coupon if isinstance(coupon, str) else None)
                discount = None
                if promo or coupon_id:
                    discount = {
                        'source': 'promotion_code' if promo else 'coupon',
                        'id': promo or coupon_id,
                        'percent_off': coupon_obj.get('percent_off'),
                        'amount_off': coupon_obj.get('amount_off') or 0,
                        'currency': coupon_obj.get('currency'),
                        'duration': coupon_obj.get('duration'),
                        'duration_in_months': coupon_obj.get('duration_in_months'),
                    }
                if discount:
                    Subscription.objects.filter(stripe_subscription_id=sub_id).update(discount=discount)
        except Exception:
            pass
        # Also process overage bundle purchases into ExtraCredits
        _credit_extras_from_invoice(obj)
    elif event_type == 'customer.subscription.deleted':
        sub_id = obj.get('id') or obj.get('subscription')
        when = _epoch_to_dt(obj.get('canceled_at')) or timezone.now()
        if sub_id:
            Subscription.objects.filter(stripe_subscription_id=sub_id).update(status='canceled', canceled_at=when)
    elif event_type == 'invoice.payment_failed':
        # Mark subscription as past_due
        sub_id = obj.get('subscription')
        if sub_id:
            Subscription.objects.filter(stripe_subscription_id=sub_id).update(status='past_due')

    return JsonResponse({'ok': True})
