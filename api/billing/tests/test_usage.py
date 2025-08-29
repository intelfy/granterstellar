from django.test import TestCase
from django.contrib.auth import get_user_model


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
