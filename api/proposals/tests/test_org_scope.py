from django.test import TestCase
from django.contrib.auth import get_user_model

from orgs.models import Organization, OrgUser
from proposals.models import Proposal


class ProposalsOrgScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="p")
        self.bob = User.objects.create_user(username="bob", password="p")
        self.org = Organization.objects.create(name="Acme", admin=self.alice)
        OrgUser.objects.create(org=self.org, user=self.alice, role="admin")
        # Bob is not a member of org

    def test_list_requires_membership(self):
        self.client.force_login(self.bob)
        # Create a proposal in the org by admin to exist in DB
        Proposal.objects.create(author=self.alice, org=self.org, content={"meta": {"title": "T"}})
        r = self.client.get("/api/proposals/", **{"HTTP_X_ORG_ID": str(self.org.id)})
        self.assertEqual(r.status_code, 200)
        # Non-member should see none
        data = r.json()
        items = data if isinstance(data, list) else data.get("results") or []
        self.assertEqual(len(items), 0)

    def test_create_falls_back_to_personal_when_not_member(self):
        self.client.force_login(self.bob)
        r = self.client.post(
            "/api/proposals/",
            data={"content": {"meta": {"title": "X"}}},
            content_type="application/json",
            **{"HTTP_X_ORG_ID": str(self.org.id)}
        )
        # Should be created in personal scope since Bob is not member
        self.assertIn(r.status_code, (201, 200))
        pid = (r.json() or {}).get("id")
        self.assertIsNotNone(pid)
        # Fetch list personal scope should include it
        r2 = self.client.get("/api/proposals/")
        self.assertEqual(r2.status_code, 200)
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("results") or []
        self.assertTrue(any(item.get("id") == pid for item in items))
