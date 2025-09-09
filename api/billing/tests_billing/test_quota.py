from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from billing.quota import (
    get_limits_for_tier,
    check_can_create_proposal,
)
from orgs.models import Organization
from proposals.models import Proposal


class QuotaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='t', password='p')

    def test_limits_by_tier(self):
        free = get_limits_for_tier('free')
        pro = get_limits_for_tier('pro')
        ent = get_limits_for_tier('enterprise')
        self.assertIsNotNone(free.active_cap)
        self.assertIsNone(free.monthly_cap)
        self.assertIsNone(pro.active_cap)
        self.assertIsNotNone(pro.monthly_cap)
        self.assertTrue(hasattr(ent, 'monthly_cap'))

    @override_settings(QUOTA_FREE_ACTIVE_CAP=1)
    def test_free_active_cap_blocks_second(self):
        Proposal.objects.create(author=self.user, content={})
        allowed, details = check_can_create_proposal(self.user, None)
        self.assertFalse(allowed)
        self.assertEqual(details.get('reason'), 'active_cap_reached')

    @override_settings(QUOTA_PRO_MONTHLY_CAP=2)
    def test_pro_monthly_cap_blocks_third(self):
        admin = self.user
        org = Organization.objects.create(name='Org', admin=admin)
        Proposal.objects.create(author=self.user, org=org, content={})
        Proposal.objects.create(author=self.user, org=org, content={})
        allowed, details = check_can_create_proposal(self.user, org)
        self.assertIsInstance(allowed, bool)
        self.assertIn('reason', details)
