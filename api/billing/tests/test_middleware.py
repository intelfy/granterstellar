from django.test import TestCase, Client


class QuotaMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_post_proposals_unauthenticated_returns_401_not_500(self):
        # Without JWT auth, the quota middleware should skip enforcement
        # and the view should enforce IsAuthenticated, returning 401
        resp = self.client.post(
            '/api/proposals/', data={'content': {'meta': {'title': 'x'}}, 'schema_version': 'v1'}, content_type='application/json'
        )
        self.assertEqual(resp.status_code, 401)
