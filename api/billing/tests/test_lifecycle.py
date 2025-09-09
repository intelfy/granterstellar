from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from billing.models import Subscription


class BillingLifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='b', password='p')
        self.client.force_login(self.user)

    def test_cancel_and_resume_debug(self):
        # No sub: 404
        resp = self.client.post('/api/billing/cancel')
        self.assertEqual(resp.status_code, 404)
        # Create a simple subscription record
        sub = Subscription.objects.create(owner_user=self.user, tier='pro', status='active')
        # Cancel
        resp = self.client.post('/api/billing/cancel')
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)
        # Resume
        resp = self.client.post('/api/billing/resume')
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertFalse(sub.cancel_at_period_end)

    @override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET='')
    def test_webhook_deleted_marks_canceled(self):
        sub = Subscription.objects.create(owner_user=self.user, tier='pro', status='active', stripe_subscription_id='sub_123')
        payload = {
            'type': 'customer.subscription.deleted',
            'data': {'object': {'id': 'sub_123', 'canceled_at': int(timezone.now().timestamp())}},
        }
        resp = self.client.post('/api/stripe/webhook', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'canceled')
        self.assertIsNotNone(sub.canceled_at)
