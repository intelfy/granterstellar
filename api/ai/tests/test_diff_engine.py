from django.test import SimpleTestCase
from ai.diff_engine import diff_texts


class DiffEngineTests(SimpleTestCase):
    def test_diff_basic(self):
        old = "Hello world\nLine2"
        new = "Hello brave world\nLine2"
        res = diff_texts(old, new)
        self.assertIsInstance(res, dict)
        self.assertIn('change_ratio', res)
        self.assertIn('blocks', res)
        self.assertGreater(res['change_ratio'], 0)
        # ensure a change block references the inserted token
        joined_after = "\n".join(b['after'] for b in res['blocks'])
        self.assertIn('brave', joined_after)
