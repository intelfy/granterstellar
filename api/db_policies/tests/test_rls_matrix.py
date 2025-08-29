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

        # Create an org and memberships as alice (admin context for inserts)
        set_guc(user_id=cls.alice.id)
        cls.org1 = Organization.objects.create(name="Org1-M", admin=cls.alice)
        set_guc(user_id=cls.alice.id)
        OrgUser.objects.create(org=cls.org1, user=cls.alice, role="admin")
        OrgUser.objects.create(org=cls.org1, user=cls.bob, role="member")

        # Create subscription for org as admin
        set_guc(user_id=cls.alice.id)
        cls.sub_org = Subscription.objects.create(owner_org=cls.org1, status="active")

    def tearDown(self):
        set_guc(None, None, "user")

    def test_member_cannot_insert_org_proposal(self):
        set_guc(self.bob.id)
        with self.assertRaises(ProgrammingError):
            Proposal.objects.create(author=self.bob, org=self.org1, content={"t": "member insert"})

    def test_admin_can_insert_org_proposal(self):
        set_guc(self.alice.id)
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "admin insert"})
        got = Proposal.objects.get(id=p.id)
        self.assertEqual(got.content.get("t"), "admin insert")

    def test_shared_with_grants_visibility(self):
        set_guc(self.alice.id)
        p = Proposal.objects.create(author=self.alice, content={"t": "shared to bob"}, shared_with=[self.bob.id])
        set_guc(self.bob.id)
        titles = {pr.content.get("t") for pr in Proposal.objects.all()}
        self.assertIn("shared to bob", titles)
        set_guc(None, None, "user")
        self.assertEqual(Proposal.objects.filter(id=p.id).count(), 0)

    def test_subscription_write_requires_admin(self):
        set_guc(self.bob.id)
        updated = Subscription.objects.filter(id=self.sub_org.id).update(status="canceled")
        self.assertEqual(updated, 0)
        set_guc(self.alice.id)
        updated2 = Subscription.objects.filter(id=self.sub_org.id).update(status="canceled")
        self.assertEqual(updated2, 1)

    def test_orguser_membership_changes_require_admin(self):
        set_guc(self.bob.id)
        with self.assertRaises(ProgrammingError):
            OrgUser.objects.create(org=self.org1, user=self.charlie)
        set_guc(self.alice.id)
        ou = OrgUser.objects.create(org=self.org1, user=self.charlie)
        deleted = OrgUser.objects.filter(id=ou.id).delete()[0]
        self.assertEqual(deleted, 1)

    def test_admin_can_delete_org_proposal_member_cannot(self):
        set_guc(self.alice.id)
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "to delete"})
        set_guc(self.bob.id)
        deleted = Proposal.objects.filter(id=p.id).delete()[0]
        self.assertEqual(deleted, 0)
        set_guc(self.alice.id)
        deleted2 = Proposal.objects.filter(id=p.id).delete()[0]
        self.assertEqual(deleted2, 1)

    def test_member_cannot_read_or_update_org_proposals(self):
        set_guc(self.alice.id)
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "org visible"})
        set_guc(self.bob.id)
        titles = {pr.content.get("t") for pr in Proposal.objects.filter(org=self.org1)}
        self.assertNotIn("org visible", titles)
        updated = Proposal.objects.filter(id=p.id).update(content={"t": "member edit"})
        self.assertEqual(updated, 0)

    def test_creator_sees_own_personal_only(self):
        set_guc(self.alice.id)
        pa = Proposal.objects.create(author=self.alice, content={"t": "alice personal"})
        set_guc(self.bob.id)
        pb = Proposal.objects.create(author=self.bob, content={"t": "bob personal"})
        set_guc(self.alice.id)
        my_titles = {pr.content.get("t") for pr in Proposal.objects.all()}
        self.assertIn("alice personal", my_titles)
        self.assertNotIn("bob personal", my_titles)
        set_guc(None, None, "user")
        self.assertEqual(Proposal.objects.filter(id__in=[pa.id, pb.id]).count(), 0)
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
            # Ensure RLS INSERT passes: act as alice (admin) for org and membership creation
            set_guc(user_id=cls.alice.id, org_id=None, role="user")
            cls.org1 = Organization.objects.create(name="Org1-M", admin=cls.alice)
            set_guc(user_id=cls.alice.id, org_id=None, role="user")
            OrgUser.objects.create(org=cls.org1, user=cls.alice)
            OrgUser.objects.create(org=cls.org1, user=cls.bob)

            # Create org subscription as admin (RLS insert check)
            set_guc(user_id=cls.alice.id, org_id=None, role="user")
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

        def test_admin_can_delete_org_proposal_member_cannot(self):
            # Admin creates an org-scoped proposal
            set_guc(self.alice.id, None, "user")
            p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "to delete"})
            # Member cannot delete (RLS blocks) → 0 rows
            set_guc(self.bob.id, None, "user")
            deleted = Proposal.objects.filter(id=p.id).delete()[0]
            self.assertEqual(deleted, 0)
            # Admin can delete → 1 row
            set_guc(self.alice.id, None, "user")
            deleted2 = Proposal.objects.filter(id=p.id).delete()[0]
            self.assertEqual(deleted2, 1)

        def test_member_cannot_read_or_update_org_proposals(self):
            # Admin creates an org-scoped proposal
            set_guc(self.alice.id, None, "user")
            p = Proposal.objects.create(author=self.alice, org=self.org1, content={"t": "org visible"})
            # Member cannot read it
            set_guc(self.bob.id, None, "user")
            titles = {pr.content.get("t") for pr in Proposal.objects.filter(org=self.org1)}
            self.assertNotIn("org visible", titles)
            # Member cannot update (RLS check should block → 0 rows)
            updated = Proposal.objects.filter(id=p.id).update(content={"t": "member edit"})
            self.assertEqual(updated, 0)

        def test_creator_sees_own_personal_only(self):
            # Alice creates personal; Bob creates personal
            set_guc(self.alice.id, None, "user")
            pa = Proposal.objects.create(author=self.alice, content={"t": "alice personal"})
            set_guc(self.bob.id, None, "user")
            pb = Proposal.objects.create(author=self.bob, content={"t": "bob personal"})
            # Alice sees her own but not Bob's
            set_guc(self.alice.id, None, "user")
            my_titles = {pr.content.get("t") for pr in Proposal.objects.all()}
            self.assertIn("alice personal", my_titles)
            self.assertNotIn("bob personal", my_titles)
            # Anonymous sees none
            set_guc(None, None, "user")
            self.assertEqual(Proposal.objects.filter(id__in=[pa.id, pb.id]).count(), 0)
