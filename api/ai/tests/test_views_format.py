from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


class AIFormatEndpointTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username="ai", password="p", email="ai@example.com")
        self.api.force_authenticate(user=self.user)

    def test_format_endpoint_returns_formatted_text(self):
        payload = {
            "full_text": "Section A\n\nContent here.",
            "template_hint": "standard",
        }
        r = self.api.post("/api/ai/format", payload, format="json")
        assert r.status_code == 200, r.content
        data = r.json()
        assert "formatted_text" in data
        # Composite routes final formatting to Gemini
        assert data["formatted_text"].startswith("[gemini:final_format")
