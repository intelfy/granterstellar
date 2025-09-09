from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model


class PortalEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='p', password='x')

    def test_requires_auth(self):
        resp = self.client.get('/api/billing/portal')
        self.assertIn(resp.status_code, (401, 403))

    @override_settings(DEBUG=True)
    def test_returns_placeholder_in_debug(self):
        self.client.force_login(self.user)
        resp = self.client.get('/api/billing/portal')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('url', data)
