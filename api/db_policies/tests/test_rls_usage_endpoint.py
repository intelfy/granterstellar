"""HTTP-level RLS tests for /api/usage (Postgres only)."""
# pyright: reportAttributeAccessIssue=false
# ruff: noqa: D,ANN

import unittest
from django.db import connection
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from orgs.models import Organization, OrgUser
from billing.models import Subscription


def set_guc(user_id=None, org_id=None, role='user'):
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ''])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ''])
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or 'user'])


@override_settings(DEBUG=False)
@unittest.skipIf(connection.vendor != 'postgresql', 'RLS tests require Postgres')
class RLSUsageEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(username='u_admin_usage', password='x')
        cls.member = User.objects.create_user(username='u_member_usage', password='x')
        cls.other = User.objects.create_user(username='u_other_usage', password='x')

        # Create org under admin context
        set_guc(user_id=cls.admin.id)
        cls.org = Organization.objects.create(name='UsageOrg', admin=cls.admin)

        # Memberships
        if connection.vendor == 'postgresql':
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(cls.admin.id)])
                cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(cls.org.id)])
                cur.execute("SELECT set_config('app.current_role', 'admin', false)")
                cur.execute(
                    'INSERT INTO orgs_orguser (org_id, user_id, role) VALUES (%s, %s, %s)',
                    [cls.org.id, cls.admin.id, 'admin'],
                )
                cur.execute(
                    'INSERT INTO orgs_orguser (org_id, user_id, role) VALUES (%s, %s, %s)',
                    [cls.org.id, cls.member.id, 'member'],
                )
        else:
            OrgUser.objects.create(org=cls.org, user=cls.admin, role='admin')
            OrgUser.objects.create(org=cls.org, user=cls.member, role='member')

        # Subscriptions
        set_guc(user_id=cls.admin.id, org_id=cls.org.id, role='admin')
        Subscription.objects.create(owner_org=cls.org, tier='pro', status='active', seats=2)
        set_guc(user_id=cls.member.id)
        Subscription.objects.create(owner_user=cls.member, tier='free', status='inactive')

    def setUp(self):
        self.client_admin = Client()
        self.client_member = Client()
        self.client_other = Client()
        assert self.client_admin.login(username='u_admin_usage', password='x')
        assert self.client_member.login(username='u_member_usage', password='x')
        assert self.client_other.login(username='u_other_usage', password='x')

    def test_anonymous_requires_auth(self):
        resp = Client().get('/api/usage')
        self.assertEqual(resp.status_code, 401)

    def test_personal_scope_member(self):
        resp = self.client_member.get('/api/usage')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('tier'), 'free')
        self.assertIn('subscription', data)

    def test_org_scope_admin(self):
        resp = self.client_admin.get('/api/usage', HTTP_X_ORG_ID=str(self.org.id))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('tier'), 'pro')
        self.assertIn('subscription', data)
        self.assertIs(data['subscription'].get('cancel_at_period_end'), False)

    def test_org_scope_member_reads_org_tier(self):
        resp = self.client_member.get('/api/usage', HTTP_X_ORG_ID=str(self.org.id))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('tier'), 'pro')
        self.assertIn('seats', data)

    def test_spoof_other_org_header_falls_back_personal(self):
        set_guc(user_id=self.other.id)
        other_org = Organization.objects.create(name='OtherOrg', admin=self.other)
        set_guc(user_id=self.other.id, org_id=other_org.id, role='admin')
        Subscription.objects.create(owner_org=other_org, tier='enterprise', status='active')

        resp = self.client_member.get('/api/usage', HTTP_X_ORG_ID=str(other_org.id))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotEqual(data.get('tier'), 'enterprise')
        self.assertEqual(data.get('tier'), 'free')
