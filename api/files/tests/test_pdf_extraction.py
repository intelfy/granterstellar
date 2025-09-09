import io
import os
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from reportlab.pdfgen import canvas


def make_simple_pdf_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.showPage()
    c.save()
    return buf.getvalue()


class PdfExtractionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_digital_pdf_text_is_extracted(self):
        data = make_simple_pdf_bytes('Hello PDF')
        up = SimpleUploadedFile('d.pdf', data, content_type='application/pdf')
        resp = self.client.post('/api/files', {'file': up}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        # We normalize whitespace; just check substring present or length > 0
        self.assertTrue(isinstance(resp.data.get('ocr_text'), str))
        self.assertGreater(len(resp.data['ocr_text']), 0)

    @override_settings(DEBUG=True)
    def test_pdf_ocr_flag_missing_binary_graceful(self):
        # Set OCR_PDF=1 but ocrmypdf binary likely missing in CI
        os.environ['OCR_PDF'] = '1'
        try:
            data = make_simple_pdf_bytes('Hello OCR')
            up = SimpleUploadedFile('o.pdf', data, content_type='application/pdf')
            resp = self.client.post('/api/files', {'file': up}, format='multipart')
            self.assertEqual(resp.status_code, 200)
            # Should still return some text (digital), or empty string gracefully if pipeline fails
            self.assertIn('ocr_text', resp.data)
            self.assertLessEqual(len(resp.data.get('ocr_text', '')), 2000)
        finally:
            os.environ.pop('OCR_PDF', None)
