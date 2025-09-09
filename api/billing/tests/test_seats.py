from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from billing.models import Subscription
from orgs.models import Organization, OrgUser


class SeatEnforcementTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.admin = U.objects.create_user(username='admin', email='admin@example.com', password='x')
        self.m1 = U.objects.create_user(username='m1', email='m1@example.com', password='x')
        self.m2 = U.objects.create_user(username='m2', email='m2@example.com', password='x')
        self.m3 = U.objects.create_user(username='m3', email='m3@example.com', password='x')
        self.c = APIClient()
        # Two orgs owned by same admin
        self.orgA = Organization.objects.create(name='A', admin=self.admin)
        self.orgB = Organization.objects.create(name='B', admin=self.admin)
        OrgUser.objects.create(org=self.orgA, user=self.admin, role='admin')
        OrgUser.objects.create(org=self.orgB, user=self.admin, role='admin')

    def test_capacity_1_blocks_third_unique_member(self):
        # Admin has 1 seat (default fallback), can include only themselves (1 unique user). To keep flow simple
        # create a subscription with 2 seats and assert we can add 1 more unique user, but third should fail.
        Subscription.objects.create(owner_user=self.admin, tier='pro', status='active', seats=2)
        self.c.force_authenticate(self.admin)
        # Add m1 to orgA (usage now: admin + m1 = 2)
        r = self.c.post(f'/api/orgs/{self.orgA.id}/members/', {'user_id': self.m1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        # Add m2 to orgB (usage would become 3 but seats=2 -> should 402)
        r = self.c.post(f'/api/orgs/{self.orgB.id}/members/', {'user_id': self.m2.id}, format='json')
        self.assertEqual(r.status_code, 402, r.content)

    def test_readding_same_user_across_admin_orgs_does_not_consume_extra(self):
        Subscription.objects.create(owner_user=self.admin, tier='pro', status='active', seats=2)
        self.c.force_authenticate(self.admin)
        # Add m1 to orgA
        r = self.c.post(f'/api/orgs/{self.orgA.id}/members/', {'user_id': self.m1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        # Add same m1 to orgB (unique users remain 2: admin + m1)
        r = self.c.post(f'/api/orgs/{self.orgB.id}/members/', {'user_id': self.m1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
