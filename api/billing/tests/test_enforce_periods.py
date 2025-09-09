from django.test import TestCase
from django.utils import timezone

from billing.models import Subscription
from django.contrib.auth import get_user_model
from django.core.management import call_command


class EnforcePeriodsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='u', password='p')

    def test_enforce_sets_canceled_after_period_end(self):
        past = timezone.now() - timezone.timedelta(days=1)
        sub = Subscription.objects.create(
            owner_user=self.user,
            tier='pro',
            status='active',
            cancel_at_period_end=True,
            current_period_end=past,
        )
        call_command('enforce_subscription_periods')
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'canceled')
        self.assertIsNotNone(sub.canceled_at)
