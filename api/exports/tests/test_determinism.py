from django.test import TestCase
from django.contrib.auth import get_user_model
from proposals.models import Proposal
from exports.utils import (
    proposal_json_to_markdown,
    render_pdf_from_text,
    render_docx_from_markdown,
    _normalize_pdf_for_checksum,
)

try:  # Prefer shared utility for checksum
    from app.common.files import compute_checksum
except Exception:  # pragma: no cover - fallback (should not normally happen)
    import hashlib as _hl

    def compute_checksum(data):  # type: ignore
        class _Obj:
            hex = _hl.sha256(data).hexdigest()

        return _Obj()

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
        # Raw markdown must be identical when generated twice from same proposal JSON
        self.assertEqual(md1, md2)
        # Checksum must also be stable
        h1 = compute_checksum(md1.encode("utf-8")).hex
        h2 = compute_checksum(md2.encode("utf-8")).hex
        self.assertEqual(h1, h2)

    def test_pdf_deterministic(self):
        md = proposal_json_to_markdown(self.proposal.content)
        pdf1, c1 = render_pdf_from_text(md)
        pdf2, c2 = render_pdf_from_text(md)
        # Contract: normalized checksum stable
        self.assertEqual(c1, c2)
        # We intentionally do NOT assert raw pdf1 == pdf2 (internal ordering may vary),
        # relying on the normalization inside render_pdf_from_text.

    def test_docx_deterministic(self):
        md = proposal_json_to_markdown(self.proposal.content)
        docx1, c1 = render_docx_from_markdown(md)
        docx2, c2 = render_docx_from_markdown(md)
        # Contract: checksum stable
        self.assertEqual(c1, c2)
        # Currently raw bytes also expected stable after zip normalization—assert to catch regressions
        self.assertEqual(compute_checksum(docx1).hex, compute_checksum(docx2).hex)

    def test_pdf_metadata_contains_deterministic_fields(self):
        md = proposal_json_to_markdown(self.proposal.content)
        pdf, checksum = render_pdf_from_text(md)
        normalized = _normalize_pdf_for_checksum(pdf)
        # Spot-check presence of deterministic metadata tokens (after normalization pass)
        self.assertIn(b'Granterstellar Export', normalized)
        self.assertIn(b'Granterstellar', normalized)
        # Creation / Mod date normalized to epoch (pattern D:19700101000000Z) after normalization
        self.assertIn(b'/CreationDate (D:19700101000000Z)', normalized)
        self.assertIn(b'/ModDate (D:19700101000000Z)', normalized)
        # Basic sanity: checksum is hex of length 64
        self.assertEqual(len(checksum), 64)

