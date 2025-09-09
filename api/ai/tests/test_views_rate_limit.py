from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(AI_ENFORCE_RATE_LIMIT_DEBUG=True, AI_RATE_PER_MIN_PRO=1, DEBUG=True)
class AIRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ratelimit', password='test12345')
        self.client = Client()
        resp = self.client.post(
            '/api/token',
            {'username': 'ratelimit', 'password': 'test12345'},
            content_type='application/json',
        )
        self.token = resp.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {self.token}'

    def test_second_write_is_limited(self):
        # Second immediate write returns 429 under single-write debug guard (AI_RATE_PER_MIN_PRO=1).
        data = {'proposal_id': 'p1', 'section_id': 's1', 'prompt': 'First'}
        # First request should succeed
        r1 = self.client.post('/api/ai/write', data=data, content_type='application/json')
        self.assertEqual(r1.status_code, 200, r1.content)
        # Second immediate request should be rate limited (429)
        r2 = self.client.post('/api/ai/write', data=data, content_type='application/json')
        self.assertEqual(r2.status_code, 429, r2.content)
        body = r2.json()
        self.assertEqual(body.get('error'), 'rate_limited')
        self.assertIn('retry_after', body)
