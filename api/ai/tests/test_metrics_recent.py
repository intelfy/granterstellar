from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ai.models import AIMetric


class AIMetricsRecentTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='mm', password='p', email='mm@example.com')
        self.api.force_authenticate(user=self.user)

    def test_recent_metrics_filtered_by_org(self):
        AIMetric.objects.create(type='write', model_id='m1', duration_ms=10, tokens_used=1, success=True, org_id='A')
        AIMetric.objects.create(type='revise', model_id='m2', duration_ms=20, tokens_used=2, success=False, org_id='B')
        AIMetric.objects.create(type='format', model_id='m3', duration_ms=30, tokens_used=3, success=True, org_id='A')

        r = self.api.get('/api/ai/metrics/recent', HTTP_X_ORG_ID='A')
        assert r.status_code == 200
        items = r.json()['items']
        assert len(items) == 2
        assert all(it['org_id'] == 'A' for it in items)

    def test_limit_capped(self):
        for i in range(0, 5):
            AIMetric.objects.create(type='write', model_id='m', duration_ms=i, tokens_used=0, success=True)
        r = self.api.get('/api/ai/metrics/recent?limit=2')
        assert r.status_code == 200
        items = r.json()['items']
        assert len(items) == 2
