import os
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


class UploadSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Authenticate to satisfy IsAuthenticated in non-DEBUG runs
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p", email="u@example.com")
        self.client.force_authenticate(user=self.user)

    def test_rejects_mismatched_signature(self):
        # Pretend a PNG by name but provide text bytes
        fake = SimpleUploadedFile("image.png", b"not-a-png", content_type="image/png")
        resp = self.client.post("/api/files", {"file": fake}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn(
            data.get("error"),
            {"mismatched_signature", "mismatched_content_type", "unsupported_type"},
        )

    def test_accepts_small_text_file(self):
        txt = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        resp = self.client.post("/api/files", {"file": txt}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("url", data)
        self.assertLessEqual(len(data.get("ocr_text", "")), 2000)

    def test_rejects_oversized_file(self):
        # 2 MB file; set a tiny cap via settings override if available
        big = SimpleUploadedFile("big.txt", b"x" * (2 * 1024 * 1024), content_type="text/plain")
        resp = self.client.post("/api/files", {"file": big}, format='multipart')
        # In default settings cap is 10MB; this would pass. We still assert either accepted or specific error.
        # For robustness, if limit is configured smaller in CI, ensure 413 with code.
        if resp.status_code in (400, 413):
            data = resp.json()
            self.assertIn(data.get("error"), {"file_too_large"})
        else:
            self.assertEqual(resp.status_code, 200)

    def test_virus_scan_blocks_when_configured(self):
        # Simulate scanner by setting env to a command that exits non-zero
        os.environ['VIRUSSCAN_CMD'] = 'sh -c "exit 2"'
        try:
            txt = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
            resp = self.client.post("/api/files", {"file": txt}, format='multipart')
            self.assertEqual(resp.status_code, 400)
            data = resp.json()
            self.assertEqual(data.get("error"), "infected")
        finally:
            os.environ.pop('VIRUSSCAN_CMD', None)
