from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from billing.models import Subscription
from orgs.models import Organization
from django.core.management import call_command


class EnforceCascadeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='adminc', password='p')
        self.member = User.objects.create_user(username='memberc', password='p')
        self.org = Organization.objects.create(name='OrgC', admin=self.admin)

    def test_enforce_downgrades_org_after_period_end(self):
        past = timezone.now() - timezone.timedelta(days=1)
        # Personal active sub that will be canceled by enforcement
        Subscription.objects.create(
            owner_user=self.admin,
            tier='pro',
            status='active',
            cancel_at_period_end=True,
            current_period_end=past,
            seats=3,
        )
        # Org currently mirrors Pro; will be recomputed to free/inactive after enforcement
        Subscription.objects.create(owner_org=self.org, tier='pro', status='active')

        call_command('enforce_subscription_periods')

        # Personal should be canceled
        personal = Subscription.objects.filter(owner_user=self.admin).order_by('-updated_at').first()
        self.assertIsNotNone(personal)
        self.assertEqual(personal.status, 'canceled')

        # Org should be downgraded to free/inactive by upsert_org_subscription_from_admin()
        org_sub = Subscription.objects.filter(owner_org=self.org).order_by('-updated_at').first()
        self.assertIsNotNone(org_sub)
        self.assertEqual(org_sub.tier, 'free')
        self.assertEqual(org_sub.status, 'inactive')
