from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from orgs.models import Organization, OrgInvite, OrgUser
from rest_framework.test import APIClient


@override_settings(DEBUG=True, GOOGLE_CLIENT_SECRET='')
class OAuthInviteAcceptTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', password='x')
        self.invitee_email = 'newuser@example.com'
        self.org = Organization.objects.create(name='Acme', admin=self.owner)
        OrgUser.objects.create(org=self.org, user=self.owner, role='admin')
        self.client = APIClient()

    def test_auto_accept_on_debug_callback_with_state(self):
        inv = OrgInvite.objects.create(org=self.org, email=self.invitee_email, role='member', invited_by=self.owner)
        # simulate debug callback: provide code + email + state=inv:<token>
        res = self.client.post(
            '/api/oauth/google/callback',
            {
                'code': 'x',
                'email': self.invitee_email,
                'state': f'inv:{inv.token}',
            },
        )
        self.assertEqual(res.status_code, 200, res.content)
        # user should exist and be member
        user = get_user_model().objects.get(email=self.invitee_email)
        self.assertTrue(OrgUser.objects.filter(org=self.org, user=user, role='member').exists())
