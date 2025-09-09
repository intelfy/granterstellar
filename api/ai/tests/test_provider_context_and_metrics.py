from django.test import TestCase
from django.contrib.auth import get_user_model


class AIProviderContextTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ai', password='p')
        self.client.force_login(self.user)

    def test_write_includes_context_block_when_file_refs(self):
        # DEBUG mode allows anonymous
        payload = {
            'section_id': 'summary',
            'answers': {'objective': 'Grow trees'},
            'file_refs': [
                {'id': 1, 'name': 'policy.pdf', 'ocr_text': 'Eligible costs include seedlings and labor.'},
                {'id': 2, 'ocr_text': 'No matching funds required.'},
            ],
        }
        resp = self.client.post('/api/ai/write', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        text = resp.json().get('draft_text', '')
        self.assertIn('[context:sources]', text)
        self.assertIn('policy.pdf', text)

    def test_revise_and_format_allow_file_refs(self):
        # revise
        resp = self.client.post(
            '/api/ai/revise',
            data={
                'section_id': 'narrative',
                'base_text': 'Base text',
                'change_request': 'polish',
                'file_refs': [{'id': 3, 'name': 'brief.txt', 'ocr_text': 'short'}],
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('[context:sources]', resp.json().get('draft_text', ''))
        # format
        resp2 = self.client.post(
            '/api/ai/format',
            data={
                'full_text': 'All content',
                'template_hint': 'default',
                'file_refs': [{'id': 9, 'name': 'guide', 'ocr_text': 'cite me'}],
            },
            content_type='application/json',
        )
        self.assertEqual(resp2.status_code, 200)
        body = resp2.json().get('formatted_text', '')
        # Composite uses Gemini for format which does not add context to header, but should not error
        self.assertIn('[gemini:final_format', body)


class AIMetricsEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='ai2', password='p')
        self.client.force_login(self.user)

    def test_metrics_recent_and_summary(self):
        # Issue a couple of calls to generate metrics rows
        self.client.post('/api/ai/write', data={'section_id': 's1', 'answers': {}}, content_type='application/json')
        self.client.post(
            '/api/ai/revise', data={'section_id': 's1', 'base_text': 'x', 'change_request': 'y'}, content_type='application/json'
        )
        # recent
        r = self.client.get('/api/ai/metrics/recent?limit=5')
        self.assertEqual(r.status_code, 200)
        items = r.json().get('items', [])
        self.assertIsInstance(items, list)
        # summary
        s = self.client.get('/api/ai/metrics/summary')
        self.assertEqual(s.status_code, 200)
        data = s.json()
        for scope in ('global', 'org', 'user'):
            self.assertIn(scope, data)
            self.assertIn('count', data[scope])
