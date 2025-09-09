from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch

from ai.models import AIJob
from ai.tasks import run_plan
from proposals.models import ProposalSection


class AsyncPlanMaterializationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='asyncplanner', password='p')

    def _create_proposal(self):
        # Use API to ensure org auto-provision path stays covered
        self.client.force_login(self.user)
        resp = self.client.post(
            '/api/proposals/',
            data={'content': {'title': 'Base Title'}},
            content_type='application/json',
        )
        assert resp.status_code in (200, 201), resp.content
        return resp.json()['id']

    def test_run_plan_creates_sections_and_persists_keys(self):
        pid = self._create_proposal()
        blueprint = [
            {'key': 'Background', 'title': 'Background', 'order': 0, 'draft': 'Bg draft'},
            {'key': 'Approach', 'title': 'Approach', 'order': 1},
        ]
        # Create pending job
        job = AIJob.objects.create(
            type='plan',
            input_json={'grant_url': 'https://example.com', 'text_spec': 'Spec'},
            created_by=self.user,
            org_id='',  # personal scope
        )
        with patch('ai.tasks._provider') as prov, patch('ai.tasks.retrieval.retrieve_for_plan', return_value=[]):
            prov.return_value.plan.return_value = {'proposal_id': pid, 'sections': blueprint}
            run_plan(job.id)  # type: ignore[attr-defined]
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        # result_json is a JSONField; runtime ensures dict when status=='done'
        self.assertIsNotNone(job.result_json)
        self.assertIn('created_sections', job.result_json)  # type: ignore[operator]
        self.assertEqual(set(job.result_json['created_sections']), {'background', 'approach'})  # type: ignore[index]
        keys = list(ProposalSection.objects.filter(proposal_id=pid).order_by('order').values_list('key', flat=True))
        self.assertEqual(keys, ['background', 'approach'])
        bg = ProposalSection.objects.get(proposal_id=pid, key='background')
        self.assertTrue(bg.draft_content.startswith('Bg draft'))
