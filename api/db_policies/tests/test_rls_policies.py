import unittest
from django.db import connection
from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization, OrgUser
from proposals.models import Proposal
# Subscription model intentionally not imported; focused RLS tests avoid coupling to billing.


def set_guc(user_id=None, org_id=None, role="user"):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ""])  # noqa: E501
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ""])  # noqa: E501
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or "user"])  # noqa: E501


def insert_org_user(org_id: int, user_id: int, role: str, acting_user_id: int):
    if connection.vendor != "postgresql":
        OrgUser.objects.create(org_id=org_id, user_id=user_id, role=role)
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(acting_user_id)])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id)])
        cur.execute("SELECT set_config('app.current_role', %s, false)", ["admin"])
        cur.execute("INSERT INTO orgs_orguser (org_id, user_id, role) VALUES (%s, %s, %s)", [org_id, user_id, role])


@unittest.skipIf(connection.vendor != "postgresql", "RLS tests require Postgres; skipped on non-Postgres backends")
class RLSPoliciesTests(TestCase):
    """Focused policy tests (org-only proposals).

    Ensures:
    - Anonymous sees nothing
    - Admin sees all org proposals (own + others + shared)
    - Member sees only their own org proposals plus those shared with them
    - Admin can update member's org proposal; member cannot update admin's
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")

        # Org and memberships
        set_guc(user_id=cls.alice.id)
        cls.org1 = Organization.objects.create(name="Org1", admin=cls.alice)
        insert_org_user(org_id=cls.org1.id, user_id=cls.alice.id, role="admin", acting_user_id=cls.alice.id)
        insert_org_user(org_id=cls.org1.id, user_id=cls.bob.id, role="member", acting_user_id=cls.alice.id)

        # Proposals (org-only)
        set_guc(user_id=cls.alice.id, org_id=cls.org1.id, role="admin")
        cls.p_alice_org = Proposal.objects.create(author=cls.alice, org=cls.org1, content={"t": "alice org"})
        set_guc(user_id=cls.alice.id, org_id=cls.org1.id, role="admin")
        cls.p_bob_org = Proposal.objects.create(author=cls.bob, org=cls.org1, content={"t": "bob org"})
        set_guc(user_id=cls.alice.id, org_id=cls.org1.id, role="admin")
        cls.p_shared = Proposal.objects.create(author=cls.bob, org=cls.org1, content={"t": "bob shared with alice"}, shared_with=[cls.alice.id])

    # Subscriptions removed from focused policy test to reduce coupling; covered elsewhere.

    def tearDown(self):
        set_guc(None, None, "user")

    def test_select_visibility_as_anonymous(self):
        set_guc(None, None, "user")
        self.assertEqual(Proposal.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)
    # No proposal/org visibility; subscription assertions omitted in focused test.

    def test_select_visibility_as_alice_admin(self):
        set_guc(self.alice.id, self.org1.id, "admin")
        titles = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertSetEqual(titles, {"alice org", "bob org", "bob shared with alice"})
        org_names = {o.name for o in Organization.objects.all()}
        self.assertSetEqual(org_names, {"Org1"})
    # Subscription visibility checks omitted.

    def test_select_visibility_as_bob_member_not_admin(self):
        set_guc(self.bob.id, self.org1.id, "user")
        titles = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertSetEqual(titles, {"bob org", "bob shared with alice"})
        org_names = {o.name for o in Organization.objects.all()}
        self.assertSetEqual(org_names, {"Org1"})
    # Subscription visibility checks omitted for member context.

    def test_update_denied_for_non_author_non_admin(self):
        set_guc(self.bob.id, self.org1.id, "user")
        updated = Proposal.objects.filter(id=self.p_alice_org.id).update(content={"t": "hacked"})
        self.assertEqual(updated, 0)

    def test_admin_can_update_org_rows(self):
        set_guc(self.alice.id, self.org1.id, "admin")
        updated = Proposal.objects.filter(id=self.p_bob_org.id).update(content={"t": "edited by admin"})
        self.assertEqual(updated, 1)
        p_bob_org = Proposal.objects.get(id=self.p_bob_org.id)
        self.assertEqual(p_bob_org.content.get("t"), "edited by admin")
