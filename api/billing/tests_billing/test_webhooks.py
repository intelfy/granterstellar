from django.test import TestCase, override_settings


class StripeWebhookTests(TestCase):
    @override_settings(DEBUG=True, STRIPE_WEBHOOK_SECRET="")
    def test_allows_unverified_event_in_debug(self):
        resp = self.client.post(
            "/api/stripe/webhook",
            data={"type": "checkout.session.completed"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False, STRIPE_WEBHOOK_SECRET="")
    def test_rejects_when_not_configured_in_prod(self):
        resp = self.client.post(
            "/api/stripe/webhook",
            data={"type": "checkout.session.completed"},
            content_type="application/json",
        )
        self.assertGreaterEqual(resp.status_code, 400)
