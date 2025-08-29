from django.test import TestCase
from django.contrib.auth import get_user_model


class ProposalsApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="apiuser", password="p")

    def test_list_endpoint_accessible_or_auth_required(self):
        resp = self.client.get("/api/proposals/")
        self.assertIn(resp.status_code, (200, 302, 401, 403))

    def test_create_one_proposal_allowed_then_blocked_by_free_cap(self):
        self.client.force_login(self.user)
        resp1 = self.client.post(
            "/api/proposals/",
            data={"content": {"title": "Test"}},
            content_type="application/json",
        )
        self.assertIn(resp1.status_code, (201, 200))
        resp2 = self.client.post(
            "/api/proposals/",
            data={"content": {"title": "Test 2"}},
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 402)
        self.assertEqual(resp2.json().get("error"), "quota_exceeded")
