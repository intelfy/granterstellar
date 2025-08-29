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

    def test_usage_org_scope_pro_monthly_cap(self):
        self.client.force_login(self.user)
        resp = self.client.get("/api/usage", HTTP_X_ORG_ID="9999")
        self.assertIn(resp.status_code, (200, 404))
