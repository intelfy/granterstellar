import json
from typing import cast
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from billing.models import Subscription


@override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET='')
class PromotionLifecycleE2ETest(TestCase):
    """Simulates a promotion lifecycle across checkout → invoice → subscription update events."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='promo_e2e', password='x')
        self.client.force_login(self.user)

    def _usage_discount(self):
        resp = self.client.get('/api/usage')
        self.assertEqual(resp.status_code, 200)
        return (resp.json().get('subscription') or {}).get('discount')

    def test_promotion_lifecycle_multi_event(self):
        # 1. checkout.session.completed with promotion
        checkout_event = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'object': 'checkout.session',
                    'id': 'cs_test_1',
                    'subscription': 'sub_e2e_1',
                    'customer': 'cus_e2e_1',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro', 'quantity': 2},
                    'discount': {
                        'promotion_code': 'promo_E2E15',
                        'coupon': {
                            'id': 'coupon_E2E15',
                            'percent_off': 15,
                            'amount_off': None,
                            'currency': 'usd',
                            'duration': 'repeating',
                            'duration_in_months': 2,
                        },
                    },
                }
            },
        }
        r1 = self.client.post('/api/stripe/webhook', data=json.dumps(checkout_event), content_type='application/json')
        self.assertEqual(r1.status_code, 200)
        sub = Subscription.objects.filter(owner_user=self.user, stripe_subscription_id='sub_e2e_1').first()
        self.assertIsNotNone(sub)
        sub = cast(Subscription, sub)
        self.assertIsNotNone(sub.discount)
        self.assertEqual(cast(dict, sub.discount).get('id'), 'promo_E2E15')
        self.assertEqual(self._usage_discount().get('id'), 'promo_E2E15')  # type: ignore[union-attr]

        # 2. invoice.paid updates quantity to 3, discount persists
        invoice_event = {
            'type': 'invoice.paid',
            'data': {
                'object': {
                    'object': 'invoice',
                    'id': 'in_e2e_1',
                    'subscription': 'sub_e2e_1',
                    'customer': 'cus_e2e_1',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro', 'quantity': 3},
                    'discount': {
                        'promotion_code': 'promo_E2E15',
                        'coupon': {
                            'id': 'coupon_E2E15',
                            'percent_off': 15,
                            'amount_off': None,
                            'currency': 'usd',
                            'duration': 'repeating',
                            'duration_in_months': 2,
                        },
                    },
                    'lines': {'data': []},
                }
            },
        }
        r2 = self.client.post('/api/stripe/webhook', data=json.dumps(invoice_event), content_type='application/json')
        self.assertEqual(r2.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.seats, 3)
        self.assertEqual(cast(dict, sub.discount).get('id'), 'promo_E2E15')
        self.assertEqual(self._usage_discount().get('id'), 'promo_E2E15')  # type: ignore[union-attr]

        # 3. subscription.updated clearing discount
        clear_event = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_e2e_1',
                    'customer': 'cus_e2e_1',
                    'metadata': {'user_id': str(self.user.pk), 'tier': 'pro'},
                    'status': 'active',
                    'discount': None,
                }
            },
        }
        r3 = self.client.post('/api/stripe/webhook', data=json.dumps(clear_event), content_type='application/json')
        self.assertEqual(r3.status_code, 200)
        sub.refresh_from_db()
        self.assertIsNone(sub.discount)
        self.assertIsNone(self._usage_discount())
