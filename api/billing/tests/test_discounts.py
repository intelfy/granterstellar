import json
from typing import cast
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from billing.models import Subscription


@override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET='')
class DiscountWebhookTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='u', password='x')
        # Create a subscription owned by user to attach updates to
        self.sub = Subscription.objects.create(
            owner_user=self.user,
            tier='pro',
            status='active',
            stripe_customer_id='cus_123',
            stripe_subscription_id='sub_123',
        )

    def post_event(self, payload: dict):
        return self.client.post('/api/stripe/webhook', data=json.dumps(payload), content_type='application/json')

    def test_subscription_updated_discount_removed_clears(self):
        # Seed with an existing discount first via queryset update to avoid type checker noise
        Subscription.objects.filter(pk=self.sub.pk).update(
            discount={
                'source': 'coupon',
                'id': 'coupon_1',
                'percent_off': 10,
                'amount_off': None,
                'currency': 'usd',
                'duration': 'once',
                'duration_in_months': 1,
            }
        )
        evt = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'object': 'subscription',
                    'id': 'sub_123',
                    'customer': 'cus_123',
                    'status': 'active',
                    'discount': None,
                    'metadata': {'user_id': str(self.user.pk)},
                }
            },
        }
        resp = self.post_event(evt)
        self.assertEqual(resp.status_code, 200)
        sub = Subscription.objects.filter(owner_user=self.user).order_by('-updated_at').first()
        sub = cast(Subscription, sub)
        self.assertIsNotNone(sub)
        self.assertIsNone(sub.discount)
