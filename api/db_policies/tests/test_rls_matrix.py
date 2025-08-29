import unittest
from django.db import connection
from django.db.utils import ProgrammingError
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
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ""])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ""])
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or "user"])


@unittest.skipIf(connection.vendor != "postgresql", "RLS tests require Postgres; skipped on non-Postgres backends")
class RLSMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice2", password="x")
        cls.bob = User.objects.create_user(username="bob2", password="x")
        cls.charlie = User.objects.create_user(username="charlie2", password="x")

        cls.org1 = Organization.objects.create(name="Org1-M", admin=cls.alice)
        OrgUser.objects.create(org=cls.org1, user=cls.alice)
        OrgUser.objects.create(org=cls.org1, user=cls.bob)

        cls.sub_org = Subscription.objects.create(owner_org=cls.org1, status="active")

    def tearDown(self):
        set_guc(None, None, "user")

    def test_member_cannot_insert_org_proposal(self):
        set_guc(self.bob.id, None, "user")
        # Postgres raises an error due to RLS WITH CHECK; sqlite won't run this test
        with self.assertRaises(ProgrammingError):
            Proposal.objects.create(author=self.bob, org=self.org1, content={"t": "member insert"})

    def test_admin_can_insert_org_proposal(self):
        set_guc(self.alice.id, None, "user")
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "admin insert"})
        # Can read back
        got = Proposal.objects.get(id=p.id)
        self.assertEqual(got.content.get("t"), "admin insert")

    def test_shared_with_grants_visibility(self):
        # Alice creates a personal proposal and shares with Bob
        set_guc(self.alice.id, None, "user")
        p = Proposal.objects.create(author=self.alice, content={"t": "shared to bob"}, shared_with=[self.bob.id])
        # Bob can see it via shared_with policy
        set_guc(self.bob.id, None, "user")
        titles = {pr.content.get("t") for pr in Proposal.objects.all()}
        self.assertIn("shared to bob", titles)
        # Anonymous cannot see it
        set_guc(None, None, "user")
        self.assertEqual(Proposal.objects.filter(id=p.id).count(), 0)

    def test_subscription_write_requires_admin(self):
        # Non-admin update should be filtered by RLS → 0 rows updated
        set_guc(self.bob.id, None, "user")
        updated = Subscription.objects.filter(id=self.sub_org.id).update(status="canceled")
        self.assertEqual(updated, 0)
        # Admin can update
        set_guc(self.alice.id, None, "user")
        updated2 = Subscription.objects.filter(id=self.sub_org.id).update(status="canceled")
        self.assertEqual(updated2, 1)

    def test_orguser_membership_changes_require_admin(self):
        # Bob (member) cannot add or remove members
        set_guc(self.bob.id, None, "user")
        with self.assertRaises(ProgrammingError):  # INSERT blocked by RLS
            OrgUser.objects.create(org=self.org1, user=self.charlie)
        # Admin can add and remove
        set_guc(self.alice.id, None, "user")
        ou = OrgUser.objects.create(org=self.org1, user=self.charlie)
        # As admin, delete should succeed
        deleted = OrgUser.objects.filter(id=ou.id).delete()[0]
        self.assertEqual(deleted, 1)
