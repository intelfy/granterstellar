from django.test import TestCase
from django.contrib.auth import get_user_model
from orgs.models import Organization, OrgUser
from proposals.models import Proposal


class ProposalsOrgScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username='alice', password='p')
        self.bob = User.objects.create_user(username='bob', password='p')
        self.org = Organization.objects.create(name='Acme', admin=self.alice)
        OrgUser.objects.create(org=self.org, user=self.alice, role='admin')

    def test_list_requires_membership(self):
        self.client.force_login(self.bob)
        Proposal.objects.create(author=self.alice, org=self.org, content={'meta': {'title': 'T'}})
        r = self.client.get('/api/proposals/', HTTP_X_ORG_ID=str(self.org.id))  # type: ignore[arg-type]
        self.assertEqual(r.status_code, 200)
        data = r.json()
        items = data if isinstance(data, list) else data.get('results') or []
        self.assertEqual(len(items), 0)

    def test_create_falls_back_to_personal_when_not_member(self):
        self.client.force_login(self.bob)
        r = self.client.post(
            '/api/proposals/',
            data={'content': {'meta': {'title': 'X'}}},
            content_type='application/json',
            HTTP_X_ORG_ID=str(self.org.id),  # type: ignore[arg-type]
        )
        self.assertIn(r.status_code, (201, 200))
        pid = (r.json() or {}).get('id')
        self.assertIsNotNone(pid)
        r2 = self.client.get('/api/proposals/')
        self.assertEqual(r2.status_code, 200)
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get('results') or []
        self.assertTrue(any(item.get('id') == pid for item in items))

    def test_personal_org_reused_across_multiple_creations(self):
        self.client.force_login(self.bob)
        first = self.client.post(
            '/api/proposals/',
            data={'content': {'meta': {'title': 'One'}}},
            content_type='application/json',
        )
        self.assertIn(first.status_code, (200, 201))
        first_org_id = first.json().get('org')
        self.assertIsNotNone(first_org_id)
        before_org_ids = set(OrgUser.objects.filter(user=self.bob).values_list('org_id', flat=True))
        second = self.client.post(
            '/api/proposals/',
            data={'content': {'meta': {'title': 'Two'}}},
            content_type='application/json',
        )
        self.assertIn(second.status_code, (200, 201, 402))
        after_org_ids = set(OrgUser.objects.filter(user=self.bob).values_list('org_id', flat=True))
        self.assertEqual(before_org_ids, after_org_ids)
        if second.status_code in (200, 201):
            self.assertEqual(second.json().get('org'), first_org_id)
