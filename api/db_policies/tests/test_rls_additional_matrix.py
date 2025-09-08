import unittest
from django.db import connection
from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization
from proposals.models import Proposal


def set_guc(user_id=None, org_id=None, role="user"):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ""])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ""])
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or "user"])


@unittest.skipIf(connection.vendor != "postgresql", "RLS tests require Postgres; skipped on non-Postgres backends")
class RLSAdditionalMatrixTests(TestCase):
    """Additional matrix ensuring cross-organization isolation and future stricter role separation.

    Focus areas (anticipating explicit OWNER/ADMIN/MEMBER policy tightening):
    - Cross-org read isolation: proposals in org A never visible under org B GUC context
    - Role downgrade does not retain elevated capabilities (simulated by changing GUC role only)
    - Anonymous user cannot see proposals even if org id GUC is set (defense-in-depth)
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adminA = User.objects.create_user(username="adminA", password="x")
        cls.adminB = User.objects.create_user(username="adminB", password="x")

        # Org A
        set_guc(user_id=cls.adminA.id)
        cls.orgA = Organization.objects.create(name="OrgA", admin=cls.adminA)
        set_guc(user_id=cls.adminA.id, org_id=cls.orgA.id, role="admin")
        cls.propA = Proposal.objects.create(author=cls.adminA, org=cls.orgA, content={"t": "A"})

        # Org B
        set_guc(user_id=cls.adminB.id)
        cls.orgB = Organization.objects.create(name="OrgB", admin=cls.adminB)
        set_guc(user_id=cls.adminB.id, org_id=cls.orgB.id, role="admin")
        cls.propB = Proposal.objects.create(author=cls.adminB, org=cls.orgB, content={"t": "B"})

    def tearDown(self):
        set_guc(None, None, "user")

    def test_cross_org_isolation(self):
        # In org A context, org B proposal should be filtered out
        set_guc(self.adminA.id, self.orgA.id, "admin")
        titlesA = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertIn("A", titlesA)
        self.assertNotIn("B", titlesA)
        # Switch to org B
        set_guc(self.adminB.id, self.orgB.id, "admin")
        titlesB = {p.content.get("t") for p in Proposal.objects.all()}
        self.assertIn("B", titlesB)
        self.assertNotIn("A", titlesB)

    def test_role_downgrade_removes_admin_capabilities(self):
        # Start as admin: can insert
        from django.db import transaction
        set_guc(self.adminA.id, self.orgA.id, "admin")
        p_new = Proposal.objects.create(author=self.adminA, org=self.orgA, content={"t": "A2"})
        self.assertIsNotNone(p_new.id)
        # Downgrade role GUC to user (simulating future stricter policy); insertion should now fail
        if connection.vendor == "postgresql":
            from django.db import ProgrammingError
            with self.assertRaises(ProgrammingError):  # Expect stricter policy to block non-admin insert
                with transaction.atomic():
                    Proposal.objects.create(author=self.adminA, org=self.orgA, content={"t": "A3"})

    def test_anonymous_sees_no_org_data(self):
        set_guc(None, self.orgA.id, "user")
        self.assertEqual(Proposal.objects.count(), 0)
