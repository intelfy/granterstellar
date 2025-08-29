from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model


class CheckoutCouponTests(TestCase):
    @override_settings(DEBUG=True, STRIPE_SECRET_KEY="")
    def test_checkout_accepts_coupon_field_in_debug(self):
        User = get_user_model()
        u = User.objects.create_user(username="c", password="p")
        self.client.force_login(u)
        resp = self.client.post("/api/billing/checkout", data={"coupon": "PROMO10"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("url", resp.json())
