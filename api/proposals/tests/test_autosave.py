from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime

from proposals.models import Proposal


class ProposalAutosaveTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="autosave", password="p")
        self.client.force_login(self.user)
        self.proposal = Proposal.objects.create(
            author=self.user,
            content={"meta": {"title": "Initial"}, "sections": {}},
        )

    def test_patch_updates_content_and_timestamp(self):
        # Capture original timestamp
        orig_ts = self.proposal.last_edited
        url = f"/api/proposals/{self.proposal.id}/"
        resp = self.client.patch(
            url,
            data={"content": {"meta": {"title": "Updated"}, "sections": {}}},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, (200, 202))
        data = resp.json()
        self.assertEqual(data["content"]["meta"]["title"], "Updated")
        # Check last_edited changed
        new_ts = parse_datetime(data["last_edited"])  # ISO string
        self.assertIsNotNone(new_ts)
        self.assertGreaterEqual(new_ts, orig_ts)
