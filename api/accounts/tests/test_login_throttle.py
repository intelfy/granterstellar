from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.urls import clear_url_caches
import importlib


class LoginThrottleTests(TestCase):
    @override_settings(DEBUG=False)
    def test_login_rate_limited(self):
        # Ensure a user exists
        User.objects.create_user(username='alice', email='a@example.com', password='secret')
        client = APIClient()

        # Ensure URLConf maps /api/token to the throttled view under DEBUG=False
        clear_url_caches()
        import app.urls  # noqa: F401

        importlib.reload(app.urls)

        # Use default 'login' throttle rate from settings (10/min); exceed it.
        # First 10 attempts should pass
        for _ in range(10):
            resp = client.post('/api/token', {'username': 'alice', 'password': 'secret'}, format='json')
            self.assertEqual(resp.status_code, 200, resp.content)

        # 11th attempt should be rate limited
        resp = client.post('/api/token', {'username': 'alice', 'password': 'secret'}, format='json')
        self.assertEqual(resp.status_code, 429)
