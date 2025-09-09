from django.test import TestCase
from django.contrib.auth import get_user_model

from billing.models import Subscription
from orgs.models import Organization


class BillingOrgLifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', password='p')
        self.member = User.objects.create_user(username='member', password='p')
        self.org = Organization.objects.create(name='Org', admin=self.admin)

    def test_admin_can_cancel_org_subscription(self):
        Subscription.objects.create(owner_org=self.org, tier='pro', status='active')
        self.client.force_login(self.admin)
        r = self.client.post('/api/billing/cancel', data={'org_id': self.org.id}, content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_member_forbidden_to_cancel_org_subscription(self):
        Subscription.objects.create(owner_org=self.org, tier='pro', status='active')
        self.client.force_login(self.member)
        r = self.client.post('/api/billing/cancel', data={'org_id': self.org.id}, content_type='application/json')
        self.assertEqual(r.status_code, 403)
