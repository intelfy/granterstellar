import json
from typing import cast
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from billing.models import Subscription


@override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET='')
class DiscountAdditionalTests(TestCase):
    """Covers remaining discount scenarios not explicitly asserted in other tests:
    - Idempotent webhook processing (same event shape twice should not change stored discount after first apply)
    - Usage endpoint reflects discount application then removal across events.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='discuser', password='p')

    def _post(self, payload: dict):
        return self.client.post('/api/stripe/webhook', data=json.dumps(payload), content_type='application/json')

    def test_idempotent_subscription_updated_discount(self):
        evt = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_same',
                    'customer': 'cus_same',
                    'status': 'active',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro'},
                    'items': {'data': [{'quantity': 2, 'price': {'id': 'price_pro_monthly'}}]},
                    'discount': {
                        'promotion_code': 'promo_same',
                        'coupon': {
                            'id': 'coupon_PROMO',
                            'percent_off': 15,
                            'amount_off': None,
                            'currency': 'usd',
                            'duration': 'once',
                            'duration_in_months': 1,
                        },
                    },
                }
            },
        }
        r1 = self._post(evt)
        self.assertEqual(r1.status_code, 200)
        r2 = self._post(evt)
        self.assertEqual(r2.status_code, 200)
        sub = Subscription.objects.filter(stripe_subscription_id='sub_same').first()
        self.assertIsNotNone(sub)
        sub = cast(Subscription, sub)
        self.assertEqual(sub.seats, 2)
        d = sub.discount or {}
        self.assertEqual(d.get('id'), 'promo_same')
        self.assertEqual(d.get('percent_off'), 15)

    def test_usage_reflects_discount_then_removal(self):
        # Apply discount
        evt_apply = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_usage',
                    'customer': 'cus_usage',
                    'status': 'active',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro'},
                    'discount': {
                        'coupon': {
                            'id': 'coupon_APPLY',
                            'percent_off': 20,
                            'amount_off': None,
                            'currency': 'usd',
                            'duration': 'once',
                            'duration_in_months': 1,
                        }
                    },
                }
            },
        }
        self._post(evt_apply)
        self.client.force_login(self.user)
        usage1 = self.client.get('/api/usage').json()['subscription']
        self.assertIsInstance(usage1.get('discount'), dict)
        self.assertEqual(usage1['discount'].get('percent_off'), 20)
        # Remove discount
        evt_remove = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_usage',
                    'customer': 'cus_usage',
                    'status': 'active',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro'},
                    'discount': None,
                }
            },
        }
        self._post(evt_remove)
        usage2 = self.client.get('/api/usage').json()['subscription']
        self.assertIsNone(usage2.get('discount'))
