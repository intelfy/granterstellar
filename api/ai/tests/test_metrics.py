from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ai.models import AIMetric


class AIMetricsTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username="m", password="p", email="m@example.com")
        self.api.force_authenticate(user=self.user)

    def test_write_records_metric(self):
        before = AIMetric.objects.count()
        payload = {"section_id": "summary", "answers": {"objective": "X"}}
        r = self.api.post("/api/ai/write", payload, format="json")
        assert r.status_code == 200
        after = AIMetric.objects.count()
        assert after == before + 1
        m = AIMetric.objects.order_by("-id").first()
        assert m.type == "write"
        assert m.duration_ms >= 0
        assert m.success is True
