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
        self.assertIn(resp.data.get("error"), {"mismatched_signature", "mismatched_content_type", "unsupported_type"})

    def test_accepts_small_text_file(self):
        txt = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        resp = self.client.post("/api/files", {"file": txt}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("url", resp.data)
        self.assertLessEqual(len(resp.data.get("ocr_text", "")), 2000)
