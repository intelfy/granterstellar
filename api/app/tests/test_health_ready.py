from django.test import TestCase, Client


class HealthReadyTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_endpoint(self):
        r = self.client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get('status'), 'ok')

    def test_ready_endpoint(self):
        r = self.client.get('/api/ready')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # DB must be ok in tests; cache may or may not be configured but key behavior should be boolean
        self.assertIn('db', data)
        self.assertTrue(data['db'])
        self.assertIn('cache', data)
        self.assertIn(data['cache'], (True, False))
        self.assertIn('status', data)
        self.assertIn(data['status'], ('ok', 'error'))
