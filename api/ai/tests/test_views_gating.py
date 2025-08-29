from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import patch


class AIGatingTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username="gate", password="p", email="gate@example.com")
        # Endpoints may be AllowAny when DEBUG at import time; authenticate anyway for clarity
        self.api.force_authenticate(user=self.user)

    @override_settings(DEBUG=False, AI_TEST_OPEN=False)
    @patch("ai.views.get_subscription_for_scope", return_value=("free", "inactive"))
    def test_free_tier_blocks_ai_endpoints(self, _mock_sub):
        # write
        r = self.api.post(
            "/api/ai/write",
            {"section_id": "summary", "answers": {"a": "b"}},
            format="json",
        )
        assert r.status_code == 402, r.content
        assert r.headers.get("X-Quota-Reason") == "ai_requires_pro"

        # revise
        r = self.api.post(
            "/api/ai/revise",
            {"base_text": "x", "change_request": "tighten"},
            format="json",
        )
        assert r.status_code == 402, r.content
        assert r.headers.get("X-Quota-Reason") == "ai_requires_pro"

        # format
        r = self.api.post(
            "/api/ai/format",
            {"full_text": "All the content"},
            format="json",
        )
        assert r.status_code == 402, r.content
        assert r.headers.get("X-Quota-Reason") == "ai_requires_pro"

    @override_settings(DEBUG=False)
    @patch("ai.views.get_subscription_for_scope", return_value=("pro", "active"))
    def test_pro_tier_allows_ai_endpoints(self, _mock_sub):
        # write allowed
        r = self.api.post(
            "/api/ai/write",
            {"section_id": "summary", "answers": {"goal": "impact"}},
            format="json",
        )
        assert r.status_code == 200, r.content
        data = r.json()
        assert "draft_text" in data

        # revise allowed
        r = self.api.post(
            "/api/ai/revise",
            {"base_text": "baseline", "change_request": "polish"},
            format="json",
        )
        assert r.status_code == 200, r.content
        data = r.json()
        assert "draft_text" in data

        # format allowed
        r = self.api.post(
            "/api/ai/format",
            {"full_text": "A B C", "template_hint": "standard"},
            format="json",
        )
        assert r.status_code == 200, r.content
        data = r.json()
        assert "formatted_text" in data

    @override_settings(DEBUG=True)
    @patch("ai.views.get_subscription_for_scope", return_value=("free", "inactive"))
    def test_debug_bypass_allows_even_free(self, _mock_sub):
        # write should pass in DEBUG regardless of tier
        r = self.api.post(
            "/api/ai/write",
            {"section_id": "budget", "answers": {"items": "list"}},
            format="json",
        )
        assert r.status_code == 200, r.content

        # revise should pass
        r = self.api.post(
            "/api/ai/revise",
            {"base_text": "t", "change_request": "expand"},
            format="json",
        )
        assert r.status_code == 200, r.content

        # format should pass
        r = self.api.post(
            "/api/ai/format",
            {"full_text": "xyz"},
            format="json",
        )
        assert r.status_code == 200, r.content
