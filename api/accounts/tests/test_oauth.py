from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.contrib.auth import get_user_model

from orgs.models import Organization, OrgInvite, OrgUser


class _CtxResp:
    def __init__(self, body: str):
        self._body = body.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


def _fake_url_from_arg(arg: Any) -> str:
    try:
        # urllib.request.Request in py3 has get_full_url
        return arg.get_full_url()  # type: ignore[attr-defined]
    except Exception:
        return str(arg)


class OAuthTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', email='admin@example.com', password='x')
        self.org = Organization.objects.create(name='Test Org', admin=self.admin)

    @override_settings(DEBUG=True)
    def test_github_debug_email_login(self):
        email = 'dev@example.com'
        res = self.client.get(
            '/api/oauth/github/callback',
            {'email': email, 'code': 'ignored'},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('email'), email)
        self.assertIn('access', data)
        self.assertIn('refresh', data)

    @override_settings(DEBUG=True)
    def test_facebook_debug_email_login(self):
        email = 'devfb@example.com'
        res = self.client.get(
            '/api/oauth/facebook/callback',
            {'email': email, 'code': 'ignored'},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('email'), email)
        self.assertIn('access', data)
        self.assertIn('refresh', data)

    @override_settings(
        DEBUG=True,
        GITHUB_CLIENT_ID='id',
        GITHUB_CLIENT_SECRET='secret',
        GITHUB_REDIRECT_URI='http://127.0.0.1:8000/api/oauth/github/callback',
    )
    def test_github_prod_flow_with_invite(self):
        # Create an invite for the email we'll return from GitHub
        email = 'gh@example.com'
        inv = OrgInvite.objects.create(org=self.org, email=email, invited_by=self.admin)

        def fake_urlopen(arg, timeout=10):  # noqa: ARG001
            url = _fake_url_from_arg(arg)
            if 'github.com/login/oauth/access_token' in url:
                return _CtxResp(json.dumps({'access_token': 'abc'}))
            if 'api.github.com/user/emails' in url:
                return _CtxResp(
                    json.dumps(
                        [
                            {'email': email, 'primary': True, 'verified': True},
                        ]
                    )
                )
            return _CtxResp('{}')

        # Patch urlopen within the accounts.oauth module
        with patch('accounts.oauth.urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.get(
                '/api/oauth/github/callback',
                {'code': 'abc', 'state': f'inv:{inv.token}'},
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('email'), email)
        # Invite should be accepted and membership created
        self.assertTrue(OrgUser.objects.filter(org=self.org, user__email=email).exists())
        inv.refresh_from_db()
        self.assertIsNotNone(inv.accepted_at)

    @override_settings(
        DEBUG=True,
        GITHUB_CLIENT_ID='id',
        GITHUB_CLIENT_SECRET='secret',
        GITHUB_REDIRECT_URI='http://127.0.0.1:8000/api/oauth/github/callback',
    )
    def test_github_prod_no_verified_emails_returns_400(self):
        email = 'unverified@example.com'

        def fake_urlopen(arg, timeout=10):  # noqa: ARG001
            url = _fake_url_from_arg(arg)
            if 'github.com/login/oauth/access_token' in url:
                return _CtxResp(json.dumps({'access_token': 'abc'}))
            if 'api.github.com/user/emails' in url:
                # Only unverified emails present
                return _CtxResp(
                    json.dumps(
                        [
                            {'email': email, 'primary': True, 'verified': False},
                            {'email': 'other@example.com', 'primary': False, 'verified': False},
                        ]
                    )
                )
            return _CtxResp('{}')

        with patch('accounts.oauth.urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.get(
                '/api/oauth/github/callback',
                {'code': 'abc'},
            )
        self.assertEqual(res.status_code, 400)

    @override_settings(
        DEBUG=True,
        GITHUB_CLIENT_ID='id',
        GITHUB_CLIENT_SECRET='secret',
        GITHUB_REDIRECT_URI='http://127.0.0.1:8000/api/oauth/github/callback',
    )
    def test_github_prod_prefers_verified_over_primary(self):
        verified_email = 'verified@example.com'
        primary_unverified = 'primary@example.com'

        def fake_urlopen(arg, timeout=10):  # noqa: ARG001
            url = _fake_url_from_arg(arg)
            if 'github.com/login/oauth/access_token' in url:
                return _CtxResp(json.dumps({'access_token': 'abc'}))
            if 'api.github.com/user/emails' in url:
                return _CtxResp(
                    json.dumps(
                        [
                            {'email': primary_unverified, 'primary': True, 'verified': False},
                            {'email': verified_email, 'primary': False, 'verified': True},
                        ]
                    )
                )
            return _CtxResp('{}')

        with patch('accounts.oauth.urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.get(
                '/api/oauth/github/callback',
                {'code': 'abc'},
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('email'), verified_email)

    @override_settings(
        DEBUG=True,
        FACEBOOK_APP_ID='id',
        FACEBOOK_APP_SECRET='secret',
        FACEBOOK_REDIRECT_URI='http://127.0.0.1:8000/api/oauth/facebook/callback',
        FACEBOOK_API_VERSION='v12.0',
    )
    def test_facebook_prod_flow_with_invite(self):
        email = 'fb@example.com'
        inv = OrgInvite.objects.create(org=self.org, email=email, invited_by=self.admin)

        def fake_urlopen(arg, timeout=10):  # noqa: ARG001
            url = _fake_url_from_arg(arg)
            if 'graph.facebook.com' in url and 'oauth/access_token' in url:
                return _CtxResp(json.dumps({'access_token': 'token'}))
            if 'graph.facebook.com' in url and '/me?' in url:
                return _CtxResp(json.dumps({'id': '1', 'name': 'F B', 'email': email}))
            return _CtxResp('{}')

        with patch('accounts.oauth.urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.get(
                '/api/oauth/facebook/callback',
                {'code': 'abc', 'state': f'inv:{inv.token}'},
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('email'), email)
        self.assertTrue(OrgUser.objects.filter(org=self.org, user__email=email).exists())
        inv.refresh_from_db()
        self.assertIsNotNone(inv.accepted_at)

    @override_settings(DEBUG=True)
    def test_cross_provider_same_email_maps_to_one_user(self):
        # First login via Google DEBUG shortcut
        email = 'same@example.com'
        res1 = self.client.get(
            '/api/oauth/google/callback',
            {'email': email, 'code': 'ignored'},
        )
        self.assertEqual(res1.status_code, 200)
        # Then login via GitHub DEBUG shortcut with same email
        res2 = self.client.get(
            '/api/oauth/github/callback',
            {'email': email, 'code': 'ignored'},
        )
        self.assertEqual(res2.status_code, 200)
        User = get_user_model()
        users = list(User.objects.filter(email__iexact=email))
        self.assertEqual(len(users), 1, 'Should link to the same account across providers')


class GoogleOAuthTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(DEBUG=True, GOOGLE_CLIENT_SECRET='')
    def test_google_callback_debug_email_shortcut(self):
        resp = self.client.post(
            '/api/oauth/google/callback',
            data={
                'code': 'dummy',
                'email': 'demo@example.com',
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode('utf-8'))
        self.assertTrue(data.get('ok'))
        self.assertIn('access', data)
        self.assertIn('refresh', data)

    @override_settings(
        DEBUG=False, GOOGLE_CLIENT_ID='client', GOOGLE_CLIENT_SECRET='secret', OAUTH_REDIRECT_URI='http://localhost/cb'
    )
    @patch('accounts.oauth._verify_google_id_token_prod')
    @patch('accounts.oauth.urllib.request.urlopen')
    def test_google_callback_prod_jwks_valid(self, mock_urlopen, mock_verify):
        # Mock token exchange response
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({'id_token': 'dummy'}).encode('utf-8')

            def decode(self, *_):
                return self.read().decode('utf-8')

        mock_urlopen.return_value = Resp()
        mock_verify.return_value = {
            'email': 'u@example.com',
            'iss': 'https://accounts.google.com',
            'aud': 'client',
        }
        resp = self.client.post('/api/oauth/google/callback', data={'code': 'abc'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode('utf-8'))
        self.assertTrue(data.get('ok'))
        self.assertIn('access', data)
        self.assertIn('refresh', data)

    @override_settings(
        DEBUG=False, GOOGLE_CLIENT_ID='client', GOOGLE_CLIENT_SECRET='secret', OAUTH_REDIRECT_URI='http://localhost/cb'
    )
    @patch('accounts.oauth._verify_google_id_token_prod')
    @patch('accounts.oauth.urllib.request.urlopen')
    def test_google_callback_prod_invalid_token(self, mock_urlopen, mock_verify):
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({'id_token': 'dummy'}).encode('utf-8')

        mock_urlopen.return_value = Resp()
        mock_verify.side_effect = ValueError('bad token')
        resp = self.client.post('/api/oauth/google/callback', data={'code': 'abc'})
        self.assertEqual(resp.status_code, 400)


class FacebookEdgeCaseTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(
        DEBUG=True,
        FACEBOOK_APP_ID='id',
        FACEBOOK_APP_SECRET='secret',
        FACEBOOK_REDIRECT_URI='http://127.0.0.1:8000/api/oauth/facebook/callback',
        FACEBOOK_API_VERSION='v12.0',
    )
    def test_facebook_prod_no_email_returns_400(self):
        def fake_urlopen(arg, timeout=10):  # noqa: ARG001
            url = _fake_url_from_arg(arg)
            if 'graph.facebook.com' in url and 'oauth/access_token' in url:
                return _CtxResp(json.dumps({'access_token': 'token'}))
            if 'graph.facebook.com' in url and '/me?' in url:
                # No email provided
                return _CtxResp(json.dumps({'id': '1', 'name': 'F B'}))
            return _CtxResp('{}')

        with patch('accounts.oauth.urllib.request.urlopen', side_effect=fake_urlopen):
            resp = self.client.get('/api/oauth/facebook/callback', data={'code': 'abc'})
        self.assertEqual(resp.status_code, 400)
