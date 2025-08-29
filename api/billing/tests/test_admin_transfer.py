from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization
from billing.models import Subscription


class AdminTransferTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.paid = User.objects.create_user(username="paid", password="p")
        self.free = User.objects.create_user(username="free", password="p")
        # Paid user has an active pro subscription
        Subscription.objects.create(owner_user=self.paid, tier="pro", status="active")
        self.org = Organization.objects.create(name="O", admin=self.free)

    def test_transfer_admin_to_paying_user_upgrades_org(self):
        # Initially free/inactive
        sub = Subscription.objects.filter(owner_org=self.org).first()
        self.assertTrue(sub is None or sub.tier in ("free",))
        # Transfer
        self.org.admin = self.paid
        self.org.save()
        org_sub = Subscription.objects.filter(owner_org=self.org).order_by("-updated_at").first()
        self.assertIsNotNone(org_sub)
        self.assertEqual(org_sub.tier, "pro")
        self.assertIn(org_sub.status, ("active", "trialing"))

    def test_transfer_admin_to_free_user_downgrades_org(self):
        # Make org pro via initial admin being paid
        self.org.admin = self.paid
        self.org.save()
        org_sub = Subscription.objects.filter(owner_org=self.org).order_by("-updated_at").first()
        self.assertEqual(org_sub.tier, "pro")
        # Transfer to free user: should downgrade
        self.org.admin = self.free
        self.org.save()
        org_sub.refresh_from_db()
        self.assertEqual(org_sub.tier, "free")
        self.assertEqual(org_sub.status, "inactive")
