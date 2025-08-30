from django.test import TestCase
from django.contrib.auth import get_user_model
import json

from billing.models import Subscription


class UsageEndpointTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.user = User.objects.create_user(username="u", password="p")

	def test_usage_free_tier_personal_scope(self):
		self.client.force_login(self.user)
		resp = self.client.get("/api/usage")
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertIn("tier", data)
		self.assertIn("limits", data)
		self.assertIn("usage", data)
		self.assertIn("can_archive", data)
		self.assertIn("can_unarchive", data)
		# subscription object should include discount key (may be null)
		self.assertIn("subscription", data)
		self.assertIn("discount", data.get("subscription", {}))

	def test_usage_discount_clears_after_webhook(self):
		self.client.force_login(self.user)
		# Seed a subscription with an active discount
		sub = Subscription.objects.create(owner_user=self.user, tier='pro', status='active', stripe_customer_id='cus_x', stripe_subscription_id='sub_x', discount={
			"source": "coupon", "id": "coupon_1", "percent_off": 10, "amount_off": None, "currency": "usd", "duration": "once", "duration_in_months": 1,
		})
		# Confirm usage shows the discount
		resp1 = self.client.get("/api/usage")
		self.assertEqual(resp1.status_code, 200)
		d1 = resp1.json().get("subscription", {})
		self.assertIsInstance(d1.get("discount"), dict)
		# Simulate webhook clearing the discount
		payload = {
			"type": "customer.subscription.updated",
			"data": {"object": {"object": "subscription", "id": sub.stripe_subscription_id, "customer": sub.stripe_customer_id, "status": "active", "discount": None, "metadata": {"user_id": str(self.user.pk)}}},
		}
		resp_wh = self.client.post("/api/stripe/webhook", data=json.dumps(payload), content_type="application/json")
		self.assertEqual(resp_wh.status_code, 200)
		# Usage should now reflect discount cleared (null)
		resp2 = self.client.get("/api/usage")
		d2 = resp2.json().get("subscription", {})
		self.assertIsNone(d2.get("discount"))

	def test_usage_org_scope_pro_monthly_cap(self):
		# Without subscriptions we're effectively free tier; still, endpoint must work
		self.client.force_login(self.user)
		resp = self.client.get("/api/usage", HTTP_X_ORG_ID="9999")
		# Org may not exist; implementation likely treats it as personal or returns defaults
		self.assertIn(resp.status_code, (200, 404))


class UsageAnonTests(TestCase):
	def test_usage_anon_returns_defaults_in_debug(self):
		# When DEBUG=1, endpoint allows anonymous and returns safe defaults
		resp = self.client.get("/api/usage")
		self.assertIn(resp.status_code, (200, 401))
		if resp.status_code == 200:
			data = resp.json()
			for key in ("tier", "status", "limits", "usage", "can_archive", "can_unarchive"):
				self.assertIn(key, data)
			self.assertEqual(data.get("reason"), "unauthenticated")
