import json
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from billing.models import Subscription


class DiscountWebhookTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="p", email="a@example.com")

    @override_settings(
        DEBUG=True,
        STRIPE_WEBHOOK_SECRET="",
        PRICE_PRO_MONTHLY="price_pro_monthly_test",
    )
    def test_subscription_updated_sets_discount_from_promotion_code(self):
        payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "object": "subscription",
                    "id": "sub_promo_123",
                    "customer": "cus_123",
                    "status": "active",
                    "metadata": {"user_id": str(self.user.id), "tier": "pro"},
                    # Seats quantity to ensure seats update path is also exercised
                    "items": {
                        "data": [
                            {"price": {"id": "price_pro_monthly_test"}, "quantity": 2}
                        ]
                    },
                    # Promotion code present → should win over coupon id
                    "discount": {
                        "promotion_code": {"id": "promo_10_off"},
                        "coupon": {
                            "id": "coupon_fallback",
                            "percent_off": 10,
                            "duration": "once",
                            "duration_in_months": 1,
                            "currency": None,
                        },
                    },
                }
            },
        }

        resp = self.client.post(
            "/api/stripe/webhook", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)

        sub = Subscription.objects.get(owner_user=self.user)
        self.assertEqual(sub.seats, 2)
        self.assertEqual(sub.tier, "pro")
        self.assertEqual(sub.status, "active")
        # Discount summary captured with promotion_code priority
        self.assertIsInstance(sub.discount, dict)
        self.assertEqual(sub.discount.get("source"), "promotion_code")
        self.assertEqual(sub.discount.get("id"), "promo_10_off")
        self.assertEqual(sub.discount.get("percent_off"), 10)
        self.assertEqual(sub.discount.get("duration"), "once")
        self.assertEqual(sub.discount.get("duration_in_months"), 1)

        # Usage reflects discount presence in subscription object
        self.client.force_login(self.user)
        uresp = self.client.get("/api/usage")
        self.assertEqual(uresp.status_code, 200)
        sub_obj = uresp.json().get("subscription", {})
        self.assertIn("discount", sub_obj)
        self.assertEqual((sub_obj.get("discount") or {}).get("id"), "promo_10_off")

    @override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET="")
    def test_invoice_paid_sets_discount_from_coupon(self):
        payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "object": "invoice",
                    "subscription": "sub_coupon_123",
                    "metadata": {"user_id": str(self.user.id), "tier": "pro"},
                    # Coupon-only path (no promotion_code)
                    "discount": {
                        "coupon": {
                            "id": "coupon_20_off",
                            "percent_off": 20,
                            "duration": "repeating",
                            "duration_in_months": 3,
                            "currency": None,
                        }
                    },
                    # Minimal lines to avoid extras crediting during this test
                    "lines": {"data": []},
                }
            },
        }

        resp = self.client.post(
            "/api/stripe/webhook", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)

        # Subscription should be created via invoice path upsert and contain coupon summary
        sub = Subscription.objects.get(owner_user=self.user)
        self.assertEqual(sub.tier, "pro")
        self.assertIsInstance(sub.discount, dict)
        self.assertEqual(sub.discount.get("source"), "coupon")
        self.assertEqual(sub.discount.get("id"), "coupon_20_off")
        self.assertEqual(sub.discount.get("percent_off"), 20)
        self.assertEqual(sub.discount.get("duration"), "repeating")
        self.assertEqual(sub.discount.get("duration_in_months"), 3)
