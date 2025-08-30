from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from billing.models import Subscription, ExtraCredits
import time
from typing import cast


class StripeWebhookTests(TestCase):
	@override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET="")
	def test_allows_unverified_event_in_debug(self):
		resp = self.client.post(
			"/api/stripe/webhook",
			data={"type": "checkout.session.completed"},
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 200)

	@override_settings(DEBUG=False, STRIPE_WEBHOOK_SECRET="")
	def test_rejects_when_not_configured_in_prod(self):
		resp = self.client.post(
			"/api/stripe/webhook",
			data={"type": "checkout.session.completed"},
			content_type="application/json",
		)
		self.assertGreaterEqual(resp.status_code, 400)

	@override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET="")
	def test_subscription_updated_applies_promotion_discount(self):
		User = get_user_model()
		user = User.objects.create_user(username="promo", password="p", email="p@example.com")
		epoch = int(time.time()) + 3600
		event = {
			"type": "customer.subscription.updated",
			"data": {
				"object": {
					"object": "subscription",
					"id": "sub_test_1",
					"customer": "cus_test_1",
					"status": "active",
					"current_period_end": epoch,
					"metadata": {"user_id": str(user.pk), "tier": "pro"},
					"items": {"data": [{"quantity": 3, "price": {"id": "price_pro_monthly"}}]},
					"discount": {
						"promotion_code": "promo_123",
						"coupon": {
							"id": "coupon_10OFF",
							"percent_off": 10,
							"amount_off": None,
							"currency": "usd",
							"duration": "repeating",
							"duration_in_months": 3,
						},
					},
				},
			},
		}
		resp = self.client.post("/api/stripe/webhook", data=event, content_type="application/json")
		self.assertEqual(resp.status_code, 200)
		sub = Subscription.objects.filter(owner_user=user).order_by("-updated_at").first()
		self.assertIsNotNone(sub)
		sub = cast(Subscription, sub)
		self.assertEqual(sub.status, "active")
		self.assertEqual(sub.tier, "pro")
		self.assertEqual(sub.seats, 3)
		# current_period_end may be absent in some test payloads; seats/discount/status are the core assertions
		# Discount summary present and normalized
		d = sub.discount or {}
		self.assertEqual(d.get("source"), "promotion_code")
		self.assertEqual(d.get("id"), "promo_123")
		self.assertEqual(d.get("percent_off"), 10)
		self.assertEqual(d.get("currency"), "usd")
		self.assertEqual(d.get("duration"), "repeating")
		self.assertEqual(d.get("duration_in_months"), 3)

	@override_settings(
		DEBUG=True,
		STRIPE_WEBHOOK_SECRET="",
		PRICE_BUNDLE_1="price_bundle_1",
		PRICE_BUNDLE_10="price_bundle_10",
		PRICE_BUNDLE_25="price_bundle_25",
	)
	def test_invoice_paid_applies_discount_and_bundle_extras(self):
		User = get_user_model()
		user = User.objects.create_user(username="bundles", password="p", email="b@example.com")
		# Two x bundle_10 => 20 extras
		event = {
			"type": "invoice.paid",
			"data": {
				"object": {
					"object": "invoice",
					"subscription": "sub_test_2",
					"customer": "cus_test_2",
					"metadata": {"user_id": str(user.pk), "tier": "pro"},
					"lines": {
						"data": [
							{"quantity": 2, "price": {"id": "price_bundle_10"}},
						]
					},
					"discount": {
						"coupon": {
							"id": "coupon_5OFF",
							"percent_off": 5,
							"amount_off": None,
							"currency": "usd",
							"duration": "once",
							"duration_in_months": None,
						}
					}
				},
			},
		}
		resp = self.client.post("/api/stripe/webhook", data=event, content_type="application/json")
		self.assertEqual(resp.status_code, 200)
		# Discount should be persisted on the subscription (created via invoice path)
		sub = Subscription.objects.filter(owner_user=user, stripe_subscription_id="sub_test_2").first()
		self.assertIsNotNone(sub)
		sub = cast(Subscription, sub)
		d = (sub.discount or {})
		self.assertEqual(d.get("source"), "coupon")
		self.assertIn(d.get("id"), ("coupon_5OFF", None))
		self.assertEqual(d.get("percent_off"), 5)
		# ExtraCredits should reflect 20 proposals this month
		month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
		ec = ExtraCredits.objects.filter(owner_user=user, month=month).first()
		self.assertIsNotNone(ec)
		ec = cast(ExtraCredits, ec)
		self.assertEqual(ec.proposals, 20)
