from django.test import SimpleTestCase
from ai.diff_engine import diff_texts


class DiffEngineTests(SimpleTestCase):
    def test_diff_basic(self):
        old = "Hello world\nLine2"
        new = "Hello brave world\nLine2"
        res = diff_texts(old, new)
        self.assertIn('brave', res.summary)
        self.assertGreater(res.change_ratio, 0)
