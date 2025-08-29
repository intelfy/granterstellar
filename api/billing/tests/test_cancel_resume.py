from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization
from billing.models import Subscription


class CancelResumeSubscriptionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="p")
        self.admin = User.objects.create_user(username="admin", password="p")
        self.member = User.objects.create_user(username="member", password="p")

    def test_cancel_and_resume_personal_subscription(self):
        # Create an active Pro subscription for the user
        sub = Subscription.objects.create(
            owner_user=self.user,
            tier="pro",
            status="active",
            cancel_at_period_end=False,
        )

        self.client.force_login(self.user)

        # Cancel at period end
        resp = self.client.post("/api/billing/cancel", data={}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertTrue(data.get("cancel_at_period_end"))
        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)

        # Resume (clear cancel_at_period_end)
        resp = self.client.post("/api/billing/resume", data={}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertFalse(data.get("cancel_at_period_end"))
        sub.refresh_from_db()
        self.assertFalse(sub.cancel_at_period_end)

    def test_cancel_org_scope_requires_admin(self):
        org = Organization.objects.create(name="Acme", admin=self.admin)
        sub = Subscription.objects.create(
            owner_org=org,
            tier="pro",
            status="active",
            cancel_at_period_end=False,
        )

        # Non-admin cannot cancel org subscription
        self.client.force_login(self.member)
        resp = self.client.post(
            "/api/billing/cancel",
            data={"org_id": org.id},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        sub.refresh_from_db()
        self.assertFalse(sub.cancel_at_period_end)

        # Admin can cancel
        self.client.force_login(self.admin)
        resp = self.client.post(
            "/api/billing/cancel",
            data={"org_id": org.id},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)

        # Admin can resume
        resp = self.client.post(
            "/api/billing/resume",
            data={"org_id": org.id},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertFalse(sub.cancel_at_period_end)

    def test_resume_returns_404_when_not_subscribed(self):
        # No subscription exists for this user
        self.client.force_login(self.user)
        resp = self.client.post("/api/billing/resume", data={}, content_type="application/json")
        self.assertEqual(resp.status_code, 404)
