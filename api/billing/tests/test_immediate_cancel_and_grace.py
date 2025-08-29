from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from orgs.models import Organization
from billing.models import Subscription
from billing.quota import get_subscription_for_scope


class ImmediateCancelAndGraceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin", password="p")
        self.org = Organization.objects.create(name="Acme", admin=self.admin)

    def test_immediate_cancel_personal_cascades_org(self):
        # Personal active sub
        personal = Subscription.objects.create(owner_user=self.admin, tier="pro", status="active")
        # Org mirrors pro (simulate prior sync)
        org_sub = Subscription.objects.create(owner_org=self.org, tier="pro", status="active")

        self.client.force_login(self.admin)
        resp = self.client.post(
            "/api/billing/cancel", data={"immediate": True}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        personal.refresh_from_db()
        org_sub.refresh_from_db()
        self.assertEqual(personal.status, "canceled")
        # Cascade should downgrade org to free/inactive via upsert
        org_sub = Subscription.objects.filter(owner_org=self.org).order_by("-updated_at").first()
        self.assertIsNotNone(org_sub)
        tier, status = get_subscription_for_scope(self.admin, self.org)
        # After immediate cancel, org should not remain pro-active
        self.assertNotEqual((tier, status), ("pro", "active"))

    @override_settings(FAILED_PAYMENT_GRACE_DAYS=3)
    def test_past_due_within_grace_allows_pro(self):
        # Past due just now -> still treated as pro within grace
        Subscription.objects.create(owner_user=self.admin, tier="pro", status="past_due")
        tier, status = get_subscription_for_scope(self.admin, None)
        self.assertEqual(tier, "pro")

    @override_settings(FAILED_PAYMENT_GRACE_DAYS=0)
    def test_past_due_no_grace_downgrades(self):
        Subscription.objects.create(owner_user=self.admin, tier="pro", status="past_due")
        tier, status = get_subscription_for_scope(self.admin, None)
        self.assertEqual(tier, "free")
