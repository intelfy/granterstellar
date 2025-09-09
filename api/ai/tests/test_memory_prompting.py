from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from ai.models import AIMemory


@override_settings(DEBUG=True)
class AIMemoryPromptingEndpointTests(TestCase):
    def setUp(self):  # noqa: D401
        self.user = get_user_model().objects.create_user(username='memuser', password='pw')
        self.client.login(username='memuser', password='pw')

    def _post(self, path: str, data: dict):
        return self.client.post(path, data, content_type='application/json')

    def test_write_includes_memory_context_when_available(self):
        # Seed two memory items for the target section
        AIMemory.record(user=self.user, org_id='', section_id='summary', key='mission', value='Reduce waste')
        AIMemory.record(user=self.user, org_id='', section_id='summary', key='impact', value='Support 2000 students')
        resp = self._post(
            '/api/ai/write',
            {
                'section_id': 'summary',
                'answers': {'objective': 'Improve access'},
            },
        )
        self.assertEqual(resp.status_code, 200)
        text = resp.json()['draft_text']
        # Marker and at least one memory line present
        self.assertIn('[context:memory]', text)
        self.assertIn('mission: Reduce waste', text)
        # Reserved key should show up in drafted bullet list as _memory_context line
        self.assertIn('_memory_context', text)
        # Ensure reserved key itself not persisted as memory row
        self.assertFalse(AIMemory.objects.filter(key='_memory_context').exists())

    def test_revise_includes_memory_context_when_available(self):
        AIMemory.record(user=self.user, org_id='', section_id='summary', key='mission', value='Reduce waste')
        resp = self._post(
            '/api/ai/revise',
            {
                'section_id': 'summary',
                'base_text': 'Base draft',
                'change_request': 'Polish style',
            },
        )
        self.assertEqual(resp.status_code, 200)
        text = resp.json()['draft_text']
        self.assertIn('[context:memory]', text)
        self.assertIn('mission: Reduce waste', text)

    def test_write_excludes_memory_context_when_none(self):
        resp = self._post(
            '/api/ai/write',
            {
                'section_id': 'summary',
                'answers': {'objective': 'Improve access'},
            },
        )
        self.assertEqual(resp.status_code, 200)
        text = resp.json()['draft_text']
        self.assertNotIn('[context:memory]', text)
