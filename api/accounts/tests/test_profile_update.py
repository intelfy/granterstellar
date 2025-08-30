from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


class ProfileUpdateTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username='alice', email='alice@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_patch_updates_username_and_email(self):
        res = self.client.patch('/api/me', {'username': 'alice2', 'email': 'alice2@example.com'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        self.assertTrue(data.get('authenticated'))
        self.assertEqual(data['user']['username'], 'alice2')
        self.assertEqual(data['user']['email'], 'alice2@example.com')

    def test_invalid_email_rejected(self):
        res = self.client.patch('/api/me', {'email': 'not-an-email'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get('error'), 'invalid_email')

    def test_no_changes(self):
        res = self.client.patch('/api/me', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get('error'), 'no_changes')
