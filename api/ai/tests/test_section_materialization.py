from django.test import TestCase
from django.contrib.auth import get_user_model
from proposals.models import ProposalSection, Proposal


class SectionMaterializationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="planner", password="p")

    def test_plan_creates_sections_from_blueprint(self):
        self.client.force_login(self.user)
        # First create a proposal to reference (planner currently expects proposal_id in payload we echo)
        # Minimal proposal create (content just placeholder); call_url optional
        p_resp = self.client.post(
            "/api/proposals/",
            data={"content": {"title": "Base"}},
            content_type="application/json",
        )
        self.assertIn(p_resp.status_code, (200, 201))
        pid = p_resp.json()["id"]
        blueprint = [
            {"key": "Introduction", "title": "Introduction", "order": 0, "draft": "Intro draft"},
            {"key": "Objectives", "title": "Objectives", "order": 1},
        ]
        # Direct planner call (sync path) - provider.plan currently echoes sanitized inputs; we emulate final shape
        # We directly call internal endpoint expecting it to parse blueprint keys and materialize.
        # Since current provider doesn't return blueprint structure, we simulate by temporarily posting blueprint
        # as if it were returned (implementation uses plan_result for blueprint extraction).
        from unittest.mock import patch
        with patch("ai.views.get_provider") as gp:
            provider = gp.return_value
            provider.plan.return_value = {"proposal_id": pid, "sections": blueprint}
            resp = self.client.post(
                "/api/ai/plan",
                data={"grant_url": "https://example.com/call", "text_spec": "Spec"},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("created_sections", body)
        self.assertEqual(set(body["created_sections"]), {"introduction", "objectives"})
        sections = ProposalSection.objects.filter(proposal_id=pid).order_by("order").values_list("key", "title")
        self.assertEqual(list(sections), [("introduction", "Introduction"), ("objectives", "Objectives")])
        intro = ProposalSection.objects.get(proposal_id=pid, key="introduction")
        self.assertTrue(intro.draft_content.startswith("Intro draft"))

    def test_plan_idempotent_updates_title_and_order(self):
        self.client.force_login(self.user)
        # Create initial proposal via API to ensure org provisioning/path consistency
        r = self.client.post(
            "/api/proposals/",
            data={"content": {"title": "X"}},
            content_type="application/json",
        )
        self.assertIn(r.status_code, (200, 201))
        p_id = r.json()["id"]
        p = Proposal.objects.get(id=p_id)
        ProposalSection.objects.create(proposal=p, key="intro", title="Old", order=5)
        new_blueprint = [
            {"key": "intro", "title": "New Intro", "order": 0},
            {"key": "methods", "title": "Methods", "order": 1},
        ]
        from unittest.mock import patch
        with patch("ai.views.get_provider") as gp:
            provider = gp.return_value
            provider.plan.return_value = {"proposal_id": p_id, "sections": new_blueprint}
            resp = self.client.post(
                "/api/ai/plan",
                data={"grant_url": "https://example.com/call", "text_spec": "Spec"},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        keys = list(ProposalSection.objects.filter(proposal=p).order_by("order").values_list("key", flat=True))
        self.assertEqual(keys, ["intro", "methods"])
        intro = ProposalSection.objects.get(proposal=p, key="intro")
        self.assertEqual(intro.title, "New Intro")
        self.assertEqual(intro.order, 0)
