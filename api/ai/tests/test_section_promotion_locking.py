from django.test import TestCase
from django.contrib.auth import get_user_model
from proposals.models import Proposal, ProposalSection
from orgs.models import Organization
from ai.models import AIJob
from ai.models import AIMetric
from rest_framework.test import APIClient
from ai.tasks import run_write, run_revise
from ai.section_pipeline import promote_section

User = get_user_model()


class SectionPromotionLockingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='pass')
        self.org = Organization.objects.create(name='Org1', admin=self.user)
        # Ensure explicit membership record (endpoint checks OrgUser, not Organization.admin)
        from orgs.models import OrgUser

        OrgUser.objects.create(org=self.org, user=self.user, role='admin')
        self.proposal = Proposal.objects.create(author=self.user, org=self.org)
        self.section = ProposalSection.objects.create(
            proposal=self.proposal,
            key='intro',
            title='Introduction',
            order=1,
        )

    def create_job(self, job_type: str, payload: dict) -> AIJob:
        return AIJob.objects.create(
            type=job_type,
            input_json=payload,
            created_by=self.user,
            org_id=str(self.org.pk),
        )

    def test_promote_locks_section(self):
        client = APIClient()
        client.login(username='user', password='pass')
        url = f'/api/sections/{self.section.id}/promote'  # noqa: E999 id attribute
        resp = client.post(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.section.refresh_from_db()
        self.assertTrue(self.section.locked)
        self.assertEqual(self.section.content, self.section.draft_content)
        self.assertTrue(AIMetric.objects.filter(type='promote', section_id=str(self.section.id)).exists())  # noqa: E999

    def test_write_aborts_when_locked(self):
        promote_section(self.section)
        job = self.create_job('write', {'section_id': str(self.section.pk), 'answers': {}})
        run_write(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'error')
        self.assertEqual(job.error_text, 'section_locked')

    def test_revise_aborts_when_locked(self):
        promote_section(self.section)
        job = self.create_job('revise', {'section_id': str(self.section.pk), 'change_request': 'shorter'})
        run_revise(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'error')
        self.assertEqual(job.error_text, 'section_locked')

    def test_unlock_allows_write(self):
        promote_section(self.section)
        self.section.locked = False
        self.section.save(update_fields=['locked'])
        job = self.create_job('write', {'section_id': str(self.section.pk), 'answers': {}})
        run_write(job.pk)
        job.refresh_from_db()
        self.assertNotEqual(job.status, 'error')
