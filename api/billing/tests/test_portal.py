from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from billing.models import Subscription


class CustomerPortalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='cp', email='cp@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @override_settings(DEBUG=True, STRIPE_SECRET_KEY='')
    def test_debug_portal_returns_placeholder_url(self):
        # No Stripe configured; should return a debug URL in DEBUG
        Subscription.objects.create(owner_user=self.user, tier='pro', status='active', stripe_customer_id='')
        res = self.client.get('/api/billing/portal')
        self.assertEqual(res.status_code, 200, res.content)
        url = res.json().get('url', '')
        self.assertTrue(url)
        self.assertIn('debug-portal=1', url)
