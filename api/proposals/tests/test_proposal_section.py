from django.test import TestCase
from django.contrib.auth import get_user_model
from orgs.models import Organization
from proposals.models import Proposal, ProposalSection


class ProposalSectionTests(TestCase):
    def test_create_section(self):
        User = get_user_model()
        user = User.objects.create(username='u1')
        org = Organization.objects.create(name='Org1', admin=user)
        prop = Proposal.objects.create(author=user, org=org, content={})
        sec = ProposalSection.objects.create(proposal=prop, key='impact', title='Impact')
        self.assertEqual(sec.key, 'impact')
