from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from orgs.models import Organization, OrgUser, OrgInvite
from billing.models import Subscription
from django.utils import timezone


class OrgInvitesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', password='x')
        self.member = User.objects.create_user(username='member', email='member@example.com', password='x')
        self.invitee = User.objects.create_user(username='invitee', email='invitee@example.com', password='x')
        self.other = User.objects.create_user(username='other', email='other@example.com', password='x')
        self.org = Organization.objects.create(name='Acme', admin=self.owner)
        # Admin and member in org
        OrgUser.objects.create(org=self.org, user=self.owner, role='admin')
        OrgUser.objects.create(org=self.org, user=self.member, role='member')
        # Ensure admin has enough seats to allow invite acceptance in tests
        Subscription.objects.create(owner_user=self.owner, tier='pro', status='active', seats=10)
        self.client = APIClient()

    def auth(self, user):
        self.client.force_authenticate(user)

    def test_owner_can_invite_list_and_revoke(self):
        self.auth(self.owner)
        # Create invite
        res = self.client.post(
            f'/api/orgs/{self.org.id}/invites/', {'email': 'invitee@example.com', 'role': 'member'}, format='json'
        )
        self.assertEqual(res.status_code, 201, res.content)
        inv_id = res.data['id']
        token = res.data['token']
        self.assertTrue(token)
        # List invites
        res = self.client.get(f'/api/orgs/{self.org.id}/invites/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        # Revoke invite
        res = self.client.delete(f'/api/orgs/{self.org.id}/invites/', {'id': inv_id}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        inv = OrgInvite.objects.get(id=inv_id)
        self.assertIsNotNone(inv.revoked_at)

    def test_member_cannot_invite(self):
        self.auth(self.member)
        res = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': 'x@example.com'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_accept_invite_success(self):
        # Owner creates invite for invitee@example.com
        self.auth(self.owner)
        res = self.client.post(
            f'/api/orgs/{self.org.id}/invites/', {'email': 'invitee@example.com', 'role': 'member'}, format='json'
        )
        token = res.data['token']
        # Accept as invitee (email must match)
        self.auth(self.invitee)
        res = self.client.post('/api/orgs/invites/accept', {'token': token}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        mu = OrgUser.objects.get(org=self.org, user=self.invitee)
        self.assertEqual(mu.role, 'member')

    def test_accept_invite_email_mismatch(self):
        self.auth(self.owner)
        res = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': 'invitee@example.com'}, format='json')
        token = res.data['token']
        # Attempt accept with other user whose email doesn't match
        self.auth(self.other)
        res = self.client.post('/api/orgs/invites/accept', {'token': token}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data.get('error'), 'email_mismatch')
        self.assertFalse(OrgUser.objects.filter(org=self.org, user=self.other).exists())

    def test_cannot_accept_revoked_or_twice(self):
        self.auth(self.owner)
        res = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': 'invitee@example.com'}, format='json')
        inv_id = res.data['id']
        token = res.data['token']
        # Revoke
        res = self.client.delete(f'/api/orgs/{self.org.id}/invites/', {'id': inv_id}, format='json')
        self.assertEqual(res.status_code, 200)
        # Try accept after revoke
        self.auth(self.invitee)
        res = self.client.post('/api/orgs/invites/accept', {'token': token}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data.get('error'), 'invite_revoked')
        # New invite
        self.auth(self.owner)
        res = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': 'invitee@example.com'}, format='json')
        token2 = res.data['token']
        self.auth(self.invitee)
        res = self.client.post('/api/orgs/invites/accept', {'token': token2}, format='json')
        self.assertEqual(res.status_code, 200)
        # Accept again with same token should fail (already_accepted)
        res = self.client.post('/api/orgs/invites/accept', {'token': token2}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data.get('error'), 'already_accepted')

    def test_invite_expiry_and_rate_limit(self):
        self.auth(self.owner)
        # Create invite and force expiry in the past
        res = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': 'exp@example.com'}, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        inv = OrgInvite.objects.get(id=res.data['id'])
        inv.expires_at = timezone.now() - timezone.timedelta(days=1)
        inv.save(update_fields=['expires_at'])
        # Attempt accept should fail with invite_expired
        from django.contrib.auth import get_user_model

        U = get_user_model()
        exp_user = U.objects.create_user(username='exp', email='exp@example.com', password='x')
        self.auth(exp_user)
        res = self.client.post('/api/orgs/invites/accept', {'token': inv.token}, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertEqual(res.data.get('error'), 'invite_expired')

        # Rate limit: create up to limit, then expect 429
        self.auth(self.owner)
        # Monkeypatch setting via override isn't available here; simulate by creating limit-1 and then assert we can still create one more,
        # then emulate rate by checking view behavior indirectly. For reliability, we create many and expect last to 429 when default=20.
        # Instead, stress to 21 to trigger default 20/hour limit.
        emails = [f'rate{i}@example.com' for i in range(21)]
        hit_429 = False
        for e in emails:
            r = self.client.post(f'/api/orgs/{self.org.id}/invites/', {'email': e}, format='json')
            if r.status_code == 429:
                hit_429 = True
                break
        self.assertTrue(hit_429, 'Expected rate limiting (429) after many invites in an hour')
