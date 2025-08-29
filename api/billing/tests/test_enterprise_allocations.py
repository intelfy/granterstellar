from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from orgs.models import Organization, OrgProposalAllocation
from billing.models import Subscription


@override_settings(DEBUG=True, QUOTA_ENTERPRISE_MONTHLY_CAP=100)
class EnterpriseAllocationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='ea_admin', email='ea@example.com', password='x')
        self.client = APIClient()
        # Two orgs owned by admin
        self.org1 = Organization.objects.create(name='O1', admin=self.admin)
        self.org2 = Organization.objects.create(name='O2', admin=self.admin)
        # Enterprise subscription for admin scope
        Subscription.objects.create(owner_user=self.admin, tier='enterprise', status='active')
        # Current month date (1st of month)
        self.month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()

    def auth(self):
        self.client.force_authenticate(self.admin)

    def test_allocation_splits_remainder_equally(self):
        self.auth()
        # Fixed allocation: org1=30, org2=0 → remaining=70 → org2 gets 70
        OrgProposalAllocation.objects.create(admin=self.admin, org=self.org1, month=self.month, allocation=30)
        res = self.client.get('/api/usage')
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        self.assertEqual(data['tier'], 'enterprise')
        eff = data.get('enterprise_effective_caps')
        # All keys are strings in response
        self.assertEqual(eff[str(self.org1.id)], 30)
        self.assertEqual(eff[str(self.org2.id)], 70)
        # enterprise_allocation detail present
        alloc = data.get('enterprise_allocation')
        self.assertIsNotNone(alloc)
        self.assertEqual(alloc['total'], 100)

    def test_allocation_fixed_overflow_caps_at_total(self):
        self.auth()
        # Fixed allocations exceed cap: org1=80, org2=50 → sum=130 > 100 → remaining=0; caps still reflect fixed
        OrgProposalAllocation.objects.create(admin=self.admin, org=self.org1, month=self.month, allocation=80)
        OrgProposalAllocation.objects.create(admin=self.admin, org=self.org2, month=self.month, allocation=50)
        res = self.client.get('/api/usage')
        self.assertEqual(res.status_code, 200, res.content)
        eff = res.json().get('enterprise_effective_caps')
        self.assertEqual(eff[str(self.org1.id)], 80)
        self.assertEqual(eff[str(self.org2.id)], 50)

