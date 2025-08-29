from django.test import Client, TestCase


class HealthTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_healthz(self):
        resp = self.client.get('/healthz')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'ok', resp.content)
