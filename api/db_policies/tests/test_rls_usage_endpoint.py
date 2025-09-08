import unittest
from django.db import connection
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from orgs.models import Organization, OrgUser
from billing.models import Subscription


@override_settings(DEBUG=False)  # Enforce authentication requirement
@unittest.skipIf(connection.vendor != "postgresql", "RLS tests require Postgres; skipped on non-Postgres backends")
class RLSUsageEndpointTests(TestCase):
    """HTTP-level RLS coverage for /api/usage.

    Validates:
    - Anonymous blocked (401) when DEBUG=False.
    - Personal scope (no X-Org-ID) returns user's personal tier.
    - Admin with X-Org-ID sees org tier.
    - Member with X-Org-ID sees org tier (read allowed).
    - Spoofed X-Org-ID of unrelated org does not leak that org's tier.
    """

    @classmethod
    def setUpTestData(cls):  # noqa: D401
        User = get_user_model()
        cls.admin = User.objects.create_user(username="u_admin_usage", password="x")
        cls.member = User.objects.create_user(username="u_member_usage", password="x")
        cls.other = User.objects.create_user(username="u_other_usage", password="x")

        cls.org = Organization.objects.create(name="UsageOrg", admin=cls.admin)
        OrgUser.objects.create(org=cls.org, user=cls.admin, role="admin")
        OrgUser.objects.create(org=cls.org, user=cls.member, role="member")

        # Org subscription (pro)
        Subscription.objects.create(owner_org=cls.org, tier="pro", status="active", seats=2)
        # Personal free (inactive) subscription record for member for symmetry
        Subscription.objects.create(owner_user=cls.member, tier="free", status="inactive")

    def setUp(self):  # fresh authenticated clients each test
        self.client_admin = Client()
        self.client_member = Client()
        self.client_other = Client()
        assert self.client_admin.login(username="u_admin_usage", password="x")
        assert self.client_member.login(username="u_member_usage", password="x")
        assert self.client_other.login(username="u_other_usage", password="x")

    # --- Tests -----------------------------------------------------------------

    def test_anonymous_requires_auth(self):
        resp = Client().get("/api/usage")
        self.assertEqual(resp.status_code, 401)

    def test_personal_scope_member(self):
        resp = self.client_member.get("/api/usage")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("tier"), "free")
        self.assertIn("subscription", data)

    def test_org_scope_admin(self):
        resp = self.client_admin.get("/api/usage", HTTP_X_ORG_ID=str(self.org.id))  # type: ignore[attr-defined]
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("tier"), "pro")
        self.assertIn("subscription", data)
        self.assertIs(data["subscription"].get("cancel_at_period_end"), False)

    def test_org_scope_member_reads_org_tier(self):
        resp = self.client_member.get("/api/usage", HTTP_X_ORG_ID=str(self.org.id))  # type: ignore[attr-defined]
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("tier"), "pro")
        self.assertIn("seats", data)

    def test_spoof_other_org_header_falls_back_personal(self):
        other_org = Organization.objects.create(name="OtherOrg", admin=self.other)
        Subscription.objects.create(owner_org=other_org, tier="enterprise", status="active")
        resp = self.client_member.get("/api/usage", HTTP_X_ORG_ID=str(other_org.id))  # type: ignore[attr-defined]
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should fall back to member's personal (free) tier; not enterprise
        self.assertNotEqual(data.get("tier"), "enterprise")
        self.assertEqual(data.get("tier"), "free")
