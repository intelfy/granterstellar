from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ai.models import AIMetric


class AIMetricsSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='u1', email='u1@example.com', password='pw')

    def test_summary_aggregates(self):
        # Seed metrics: 1 write, 2 revise for same user/org
        org_id = 'orgA'
        AIMetric.objects.create(
            type='write', model_id='m', tokens_used=100, duration_ms=1000, success=True, created_by=self.user, org_id=org_id
        )
        AIMetric.objects.create(
            type='revise', model_id='m', tokens_used=50, duration_ms=500, success=True, created_by=self.user, org_id=org_id
        )
        AIMetric.objects.create(
            type='revise', model_id='m', tokens_used=150, duration_ms=1500, success=True, created_by=self.user, org_id=org_id
        )

        # Authenticate to populate user bucket
        self.client.force_authenticate(self.user)
        resp = self.client.get('/api/ai/metrics/summary', HTTP_X_ORG_ID=org_id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('global', data)
        self.assertIn('org', data)
        self.assertIn('user', data)

        # Global expectations
        g = data['global']
        self.assertEqual(g['count'], 3)
        self.assertAlmostEqual(g['avg_tokens'], 100.0, places=2)
        self.assertAlmostEqual(g['avg_duration_ms'], 1000.0, places=2)
        # Edits: two entries by same user => avg per user == 2.0; avg edit tokens == 100.0
        self.assertAlmostEqual(g['edits_per_user_avg'], 2.0, places=2)
        self.assertAlmostEqual(g['edit_tokens_avg'], 100.0, places=2)

        # Org and User should mirror global for this dataset
        o = data['org']
        self.assertEqual(o['count'], 3)
        self.assertAlmostEqual(o['avg_tokens'], 100.0, places=2)
        u = data['user']
        self.assertEqual(u['count'], 3)
        self.assertAlmostEqual(u['avg_tokens'], 100.0, places=2)
