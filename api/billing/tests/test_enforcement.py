from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model
from orgs.models import Organization
from billing.models import Subscription


class EnforcementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='alice', email='a@example.com', password='x')
        self.org = Organization.objects.create(name='Acme', admin=self.user)

    def test_cancel_and_downgrade_cascade(self):
        # Personal sub set to cancel at period end, already passed
        sub = Subscription.objects.create(
            owner_user=self.user,
            tier='pro',
            status='active',
            cancel_at_period_end=True,
            current_period_end=timezone.now() - timedelta(days=1),
        )
        # Seed an org subscription mirroring pro
        Subscription.objects.create(owner_org=self.org, tier='pro', status='active')

        call_command('enforce_subscription_periods')

        sub.refresh_from_db()
        self.assertEqual(sub.status, 'canceled')
        # Org should mirror admin becoming free/inactive
        org_sub = Subscription.objects.filter(owner_org=self.org).order_by('-updated_at').first()
        self.assertIsNotNone(org_sub)
        self.assertEqual(org_sub.tier, 'free')
        self.assertIn(org_sub.status, ('inactive', 'canceled'))
