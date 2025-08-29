from django.test import TestCase, override_settings


class GoogleOAuthTests(TestCase):
    @override_settings(GOOGLE_CLIENT_ID='id', OAUTH_REDIRECT_URI='http://localhost/callback')
    def test_google_start_requires_config(self):
        resp = self.client.get('/api/oauth/google/start')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('auth_url', resp.json())

    @override_settings(DEBUG=True, GOOGLE_CLIENT_ID='id', OAUTH_REDIRECT_URI='http://localhost/callback')
    def test_google_callback_debug_shortcut_requires_email(self):
        # missing email
        resp = self.client.post('/api/oauth/google/callback', data={'code': 'x'})
        self.assertGreaterEqual(resp.status_code, 400)

    @override_settings(DEBUG=True, GOOGLE_CLIENT_ID='id', OAUTH_REDIRECT_URI='http://localhost/callback')
    def test_google_callback_debug_shortcut_with_email(self):
        resp = self.client.post('/api/oauth/google/callback', data={'code': 'x', 'email': 'alice@example.com'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
