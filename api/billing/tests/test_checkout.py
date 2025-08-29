from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model


class CheckoutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="checkout_user", password="p")
        self.client.force_login(self.user)

    @override_settings(DEBUG=True, STRIPE_SECRET_KEY="")
    def test_checkout_debug_placeholder(self):
        resp = self.client.post("/api/billing/checkout", data={}, content_type="application/json")
        # In DEBUG without Stripe keys, we expect a URL placeholder
        self.assertEqual(resp.status_code, 200)
        self.assertIn("url", resp.json())
