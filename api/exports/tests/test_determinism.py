from django.test import TestCase
from django.contrib.auth import get_user_model
from proposals.models import Proposal
from exports.utils import proposal_json_to_markdown, render_pdf_from_text, render_docx_from_markdown
import hashlib

class ExportDeterminismTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username="e", password="p")
        self.proposal = Proposal.objects.create(
            author=self.user,
            content={
                "meta": {"title": "Deterministic"},
                "sections": {
                    "summary": {"title": "Executive Summary", "content": "Hello world"},
                    "plan": {"title": "Plan", "content": "Do X\nThen Y"},
                },
            },
        )

    def test_markdown_checksum_stable(self):
        md1 = proposal_json_to_markdown(self.proposal.content)
        md2 = proposal_json_to_markdown(self.proposal.content)
        self.assertEqual(md1, md2)
        h1 = hashlib.sha256(md1.encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(md2.encode("utf-8")).hexdigest()
        self.assertEqual(h1, h2)

    def test_pdf_deterministic(self):
        md = proposal_json_to_markdown(self.proposal.content)
        pdf1, c1 = render_pdf_from_text(md)
        pdf2, c2 = render_pdf_from_text(md)
        self.assertEqual(c1, c2)
    # Raw PDF bytes may differ due to internal object ordering; checksum is computed on a normalized form
    # so comparing raw bytes isn't reliable. The stable contract is checksum equality.

    def test_docx_deterministic(self):
        md = proposal_json_to_markdown(self.proposal.content)
        docx1, c1 = render_docx_from_markdown(md)
        docx2, c2 = render_docx_from_markdown(md)
        self.assertEqual(c1, c2)
        self.assertEqual(hashlib.sha256(docx1).hexdigest(), hashlib.sha256(docx2).hexdigest())
