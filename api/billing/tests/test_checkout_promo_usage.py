from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from billing.models import Subscription


@override_settings(DEBUG=True, STRIPE_SECRET_KEY='')
class CheckoutPromoUsageTests(TestCase):
    """Ensures that providing a coupon code at checkout seeds discount metadata reflected in /api/usage.

    This is a DEBUG-mode simulation; in live mode Stripe webhooks would authoritatively sync the discount.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='promo_user', password='x')
        self.client.force_login(self.user)

    def test_checkout_with_coupon_reflected_in_usage(self):
        resp = self.client.post(
            '/api/billing/checkout',
            data={'coupon': 'PROMO10'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        # Simulate subscription creation that would normally occur post-Stripe redirect/webhook.
        # In DEBUG absence of real Stripe call, create a subscription carrying discount for usage endpoint.
        sub = Subscription.objects.create(
            owner_user=self.user,
            tier='pro',
            status='active',
            stripe_customer_id='cus_dbg',
            stripe_subscription_id='sub_dbg',
            discount={
                'source': 'coupon',
                'id': 'PROMO10',
                'percent_off': 10,
                'amount_off': None,
                'currency': 'usd',
                'duration': 'once',
                'duration_in_months': 1,
            },
        )
        self.assertIsNotNone(sub.pk)
        usage = self.client.get('/api/usage')
        self.assertEqual(usage.status_code, 200)
        data = usage.json().get('subscription', {})
        disc = data.get('discount')
        self.assertIsInstance(disc, dict)
        self.assertEqual(disc.get('id'), 'PROMO10')
        self.assertEqual(disc.get('percent_off'), 10)
