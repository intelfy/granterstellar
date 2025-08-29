import unittest
from django.db import connection
from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization, OrgUser
from proposals.models import Proposal
from billing.models import Subscription


def set_guc(user_id=None, org_id=None, role="user"):
    """Set Postgres GUCs used by RLS policies; no-op on non-Postgres backends."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_user_id', %s, false)",
            [str(user_id) if user_id else ""],
        )
        cur.execute(
            "SELECT set_config('app.current_org_id', %s, false)",
            [str(org_id) if org_id else ""],
        )
        cur.execute(
            "SELECT set_config('app.current_role', %s, false)",
            [role or "user"],
        )


@unittest.skipIf(connection.vendor != "postgresql", "RLS tests require Postgres; skipped on non-Postgres backends")
class RLSPoliciesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")

        cls.org1 = Organization.objects.create(name="Org1", admin=cls.alice)
        OrgUser.objects.create(org=cls.org1, user=cls.alice)
        OrgUser.objects.create(org=cls.org1, user=cls.bob)

        # Proposals: personal and org-scoped
        cls.p1 = Proposal.objects.create(author=cls.alice, content={"t": "alice personal"})
        cls.p2 = Proposal.objects.create(author=cls.bob, content={"t": "bob personal"})
        cls.p3 = Proposal.objects.create(author=cls.alice, org=cls.org1, content={"t": "alice org"})
        cls.p4 = Proposal.objects.create(author=cls.bob, org=cls.org1, content={"t": "bob org"})
        cls.p5 = Proposal.objects.create(
            author=cls.bob,
            content={"t": "bob shared with alice"},
            shared_with=[cls.alice.id],
        )

        # Subscriptions: user-owned and org-owned
        cls.sub_user = Subscription.objects.create(owner_user=cls.alice, status="active")
        cls.sub_org = Subscription.objects.create(owner_org=cls.org1, status="active")

    def tearDown(self):
        # Reset GUCs between tests
        set_guc(None, None, "user")

    def test_select_visibility_as_anonymous(self):
        set_guc(None, None, "user")
        self.assertEqual(Proposal.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_select_visibility_as_alice_admin(self):
        set_guc(self.alice.id, None, "user")
        # Alice sees: her personal (p1), org proposals where she's admin (p3, p4), and shared-to-her (p5)
        titles = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertSetEqual(titles, {"alice personal", "alice org", "bob org", "bob shared with alice"})

        # Org read: alice can see her org
        org_names = {o.name for o in Organization.objects.all()}
        self.assertSetEqual(org_names, {"Org1"})

        # Subscriptions: alice sees her user sub and the org sub (admin)
        subs = list(Subscription.objects.all())
        self.assertEqual(len(subs), 2)
        self.assertTrue(any(s.owner_user_id == self.alice.id for s in subs))
        self.assertTrue(any(s.owner_org_id == self.org1.id for s in subs))

    def test_select_visibility_as_bob_member_not_admin(self):
        set_guc(self.bob.id, None, "user")
        # Bob sees only his personal and items shared with him (none), not org proposals (admin-only)
        titles = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertSetEqual(titles, {"bob personal"})

        # Org read: policy allows members to read their org
        org_names = {o.name for o in Organization.objects.all()}
        self.assertSetEqual(org_names, {"Org1"})

        # Subscriptions: Bob should not see org subscription (not admin), only user-owned if any (none)
        subs = list(Subscription.objects.all())
        self.assertEqual(len(subs), 0)

    def test_update_denied_for_non_author_non_admin(self):
        set_guc(self.bob.id, None, "user")
        # Bob cannot see/update alice's personal or org proposals
        with self.assertRaises(Proposal.DoesNotExist):
            Proposal.objects.get(id=self.p1.id)
        with self.assertRaises(Proposal.DoesNotExist):
            Proposal.objects.get(id=self.p3.id)

        # Update via queryset should affect 0 rows when RLS denies
        updated = Proposal.objects.filter(id=self.p3.id).update(content={"t": "hacked"})
        self.assertEqual(updated, 0)

    def test_admin_can_update_org_rows(self):
        set_guc(self.alice.id, None, "user")
        # As admin, Alice can update org proposals
        updated = Proposal.objects.filter(id=self.p4.id).update(content={"t": "edited by admin"})
        self.assertEqual(updated, 1)
        p4 = Proposal.objects.get(id=self.p4.id)
        self.assertEqual(p4.content.get("t"), "edited by admin")
