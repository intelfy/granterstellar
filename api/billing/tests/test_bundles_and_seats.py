import json
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from billing.models import Subscription, ExtraCredits


class BundlesAndSeatsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='u', password='p', email='u@example.com')

    @override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET='', PRICE_BUNDLE_10='price_bundle10_test')
    def test_invoice_bundle_credits_and_usage_extras(self):
        # Simulate an invoice payment with a 10-pack bundle purchased twice (qty=2) → 20 extras
        payload = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'object': 'invoice',
                    'metadata': {'user_id': str(self.user.id)},
                    'lines': {
                        'data': [
                            {
                                'price': {'id': 'price_bundle10_test'},
                                'quantity': 2,
                            }
                        ]
                    },
                }
            },
        }
        resp = self.client.post(
            '/api/stripe/webhook',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        # Extras credited for current month
        month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        ec = ExtraCredits.objects.get(owner_user=self.user, month=month)
        self.assertEqual(ec.proposals, 20)

        # Usage endpoint exposes extras even if not Pro
        self.client.force_login(self.user)
        uresp = self.client.get('/api/usage')
        self.assertEqual(uresp.status_code, 200)
        data = uresp.json()
        self.assertIn('limits', data)
        self.assertEqual(data['limits'].get('extras'), 20)

        # When Pro with 1 seat, monthly cap = seats*per_seat + extras = 10 + 20 = 30
        Subscription.objects.create(
            owner_user=self.user,
            tier='pro',
            status='active',
            stripe_customer_id='cus_test',
            stripe_subscription_id='sub_test',
            seats=1,
        )
        uresp2 = self.client.get('/api/usage')
        self.assertEqual(uresp2.status_code, 200)
        self.assertEqual(uresp2.json()['limits'].get('monthly_cap'), 30)

    @override_settings(
        DEBUG=True,
        STRIPE_WEBHOOK_SECRET='',
        PRICE_PRO_MONTHLY='price_pro_test',
        QUOTA_PRO_PER_SEAT=10,
    )
    def test_subscription_update_sets_seats_and_usage_reflects(self):
        # Simulate customer.subscription.updated with quantity=3
        payload = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_123',
                    'customer': 'cus_123',
                    'status': 'active',
                    'metadata': {'user_id': str(self.user.id), 'tier': 'pro'},
                    'items': {
                        'data': [
                            {
                                'price': {'id': 'price_pro_test'},
                                'quantity': 3,
                            }
                        ]
                    },
                }
            },
        }
        resp = self.client.post(
            '/api/stripe/webhook',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        sub = Subscription.objects.get(owner_user=self.user)
        self.assertEqual(sub.seats, 3)
        self.assertEqual(sub.tier, 'pro')
        self.assertEqual(sub.status, 'active')

        # Usage monthly cap should be seats * QUOTA_PRO_PER_SEAT = 3 * 10 = 30
        self.client.force_login(self.user)
        uresp = self.client.get('/api/usage')
        self.assertEqual(uresp.status_code, 200)
        self.assertEqual(uresp.json()['limits'].get('monthly_cap'), 30)
