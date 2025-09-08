from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from ai.models import AIMemory


@override_settings(DEBUG=True)
class AIMemorySuggestionsViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='viewer', password='pw')
        self.client.login(username='viewer', password='pw')

    def _auth_get(self, path, **headers):  # helper for authenticated GET with optional org header
        return self.client.get(path, **{"HTTP_X_ORG_ID": headers.get('org_id', '')})

    def test_empty_initial(self):
        resp = self._auth_get('/api/ai/memory/suggestions')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['items'], [])

    def test_user_scope_records_returned(self):
        AIMemory.record(user=self.user, org_id='', section_id='intro', key='mission', value='Reduce waste')
        resp = self._auth_get('/api/ai/memory/suggestions?section_id=intro')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['items']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['key'], 'mission')

    def test_org_scope_isolated_from_personal(self):
        AIMemory.record(user=self.user, org_id='123', section_id='impact', key='beneficiaries', value='2000 students')
        # Org scoped fetch should return the item
        resp_org = self._auth_get('/api/ai/memory/suggestions?section_id=impact', org_id='123')
        self.assertEqual(resp_org.status_code, 200)
        self.assertEqual(len(resp_org.json()['items']), 1)
        # User (no org header) should NOT see org-scoped memory
        resp_user = self._auth_get('/api/ai/memory/suggestions?section_id=impact')
        self.assertEqual(resp_user.status_code, 200)
        self.assertEqual(resp_user.json()['items'], [])

    def test_limit_enforced(self):
        for i in range(8):
            AIMemory.record(user=self.user, org_id='', section_id='cap', key=f'k{i}', value=f'v{i}')
        resp = self._auth_get('/api/ai/memory/suggestions?section_id=cap&limit=3')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['items']), 3)

    def test_unauthenticated_returns_empty(self):
        self.client.logout()
        resp = self.client.get('/api/ai/memory/suggestions')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['items'], [])
