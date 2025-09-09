import unittest
from django.db import connection
from django.db.utils import ProgrammingError
from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization, OrgUser
from proposals.models import Proposal
from billing.models import Subscription


def set_guc(user_id=None, org_id=None, role: 'str' = 'user'):
    """Set Postgres GUCs used by RLS policies; no-op on non-Postgres backends."""
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ''])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ''])
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or 'user'])


@unittest.skipIf(connection.vendor != 'postgresql', 'RLS tests require Postgres; skipped on non-Postgres backends')
class RLSMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Create baseline users, an organization (alice as admin), and a subscription.

        All work is performed inside this classmethod so that references to ``cls``
        are valid. Previous failures came from mis-indented lines sitting at
        class scope. Keep all setup inside this method body.
        """
        User = get_user_model()
        cls.alice = User.objects.create_user(username='alice2', password='x')
        cls.bob = User.objects.create_user(username='bob2', password='x')
        cls.charlie = User.objects.create_user(username='charlie2', password='x')

        # Create organization (alice admin context)
        set_guc(user_id=cls.alice.id)
        cls.org1 = Organization.objects.create(name='Org1-M', admin=cls.alice)

        # Org subscription (admin GUC context)
        set_guc(user_id=cls.alice.id, org_id=cls.org1.id, role='admin')
        cls.sub_org = Subscription.objects.create(owner_org=cls.org1, status='active')
        set_guc(None, None, 'user')

    def tearDown(self):  # reset GUCs between tests
        set_guc(None, None, 'user')

    def test_member_cannot_insert_org_proposal(self):
        from django.db import transaction

        set_guc(self.bob.id)  # bob not admin nor member
        with self.assertRaises(ProgrammingError):
            with transaction.atomic():
                Proposal.objects.create(author=self.bob, org=self.org1, content={'t': 'member insert'})

    def test_admin_can_insert_org_proposal(self):
        # Must set org + role admin for insert per 0011 granular policies
        set_guc(self.alice.id, self.org1.id, 'admin')
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={'t': 'admin insert'})
        self.assertEqual(Proposal.objects.get(id=p.id).content.get('t'), 'admin insert')

    def test_shared_with_grants_visibility(self):
        # Admin creates and shares an org-scoped proposal
        set_guc(self.alice.id, self.org1.id, 'admin')
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={'t': 'shared to bob'}, shared_with=[self.bob.id])
        set_guc(self.bob.id)
        titles = {pr.content.get('t') for pr in Proposal.objects.all()}
        self.assertIn('shared to bob', titles)
        set_guc(None, None, 'user')
        self.assertEqual(Proposal.objects.filter(id=p.id).count(), 0)

    def test_subscription_write_requires_admin(self):
        set_guc(self.bob.id)
        self.assertEqual(Subscription.objects.filter(id=self.sub_org.id).update(status='canceled'), 0)
        set_guc(self.alice.id)
        self.assertEqual(Subscription.objects.filter(id=self.sub_org.id).update(status='canceled'), 1)

    def test_orguser_membership_changes_require_admin(self):
        from django.db import transaction

        set_guc(self.bob.id, self.org1.id, 'member')
        with self.assertRaises(ProgrammingError):
            with transaction.atomic():
                OrgUser.objects.create(org=self.org1, user=self.charlie, role='member')

    def test_admin_can_delete_org_proposal_member_cannot(self):
        set_guc(self.alice.id, self.org1.id, 'admin')
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={'t': 'to delete'})
        set_guc(self.bob.id)
        self.assertEqual(Proposal.objects.filter(id=p.id).delete()[0], 0)
        set_guc(self.alice.id, self.org1.id, 'admin')
        self.assertEqual(Proposal.objects.filter(id=p.id).delete()[0], 1)

    def test_member_cannot_read_or_update_org_proposals(self):
        set_guc(self.alice.id, self.org1.id, 'admin')
        p = Proposal.objects.create(author=self.alice, org=self.org1, content={'t': 'org visible'})
        set_guc(self.bob.id)
        titles = {pr.content.get('t') for pr in Proposal.objects.filter(org=self.org1)}
        self.assertNotIn('org visible', titles)
        self.assertEqual(Proposal.objects.filter(id=p.id).update(content={'t': 'member edit'}), 0)

    @unittest.skip('Personal proposals removed: org_id now mandatory; legacy personal test deprecated.')
    def test_creator_sees_own_personal_only(self):  # pragma: no cover - intentionally skipped
        pass
