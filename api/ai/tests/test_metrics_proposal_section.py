from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ai.models import AIMetric


class AIMetricsProposalSectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(username='u2', email='u2@example.com', password='pw')
        self.client.force_authenticate(self.user)

    def test_write_records_proposal_and_section(self):
        payload = {
            'proposal_id': 123,
            'section_id': 's1',
            'answers': {'q': 'a'},
            'file_refs': [],
        }
        resp = self.client.post('/api/ai/write', payload, format='json', HTTP_X_ORG_ID='orgX')
        self.assertEqual(resp.status_code, 200)
        m = AIMetric.objects.filter(type='write').order_by('-id').first()
        self.assertIsNotNone(m)
        self.assertEqual(m.proposal_id, 123)
        self.assertEqual(m.section_id, 's1')

    def test_revise_records_proposal_and_section(self):
        payload = {
            'proposal_id': 456,
            'section_id': 's2',
            'base_text': 'hello',
            'change_request': 'shorter',
            'file_refs': [],
        }
        resp = self.client.post('/api/ai/revise', payload, format='json', HTTP_X_ORG_ID='orgY')
        self.assertEqual(resp.status_code, 200)
        m = AIMetric.objects.filter(type='revise').order_by('-id').first()
        self.assertIsNotNone(m)
        self.assertEqual(m.proposal_id, 456)
        self.assertEqual(m.section_id, 's2')
