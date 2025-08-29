from django.test import TestCase
from exports.utils import proposal_json_to_markdown, render_pdf_from_text, render_docx_from_markdown


class ExportEscapeTests(TestCase):
    def test_markdown_escapes_html(self):
        proposal = {
            "meta": {"title": "<b>Title</b>"},
            "sections": {
                "s1": {"title": "Intro", "content": "Hello <script>alert(1)</script>"}
            }
        }
        md = proposal_json_to_markdown(proposal)
        self.assertIn("&lt;b&gt;Title&lt;/b&gt;", md)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", md)

    def test_renderers_accept_text(self):
        text = "Hello\nWorld"
        pdf, sum1 = render_pdf_from_text(text)
        self.assertTrue(isinstance(pdf, (bytes, bytearray)))
        self.assertEqual(len(sum1), 64)
        md = "# T\n\nBody"
        docx, sum2 = render_docx_from_markdown(md)
        self.assertTrue(isinstance(docx, (bytes, bytearray)))
        self.assertEqual(len(sum2), 64)
