from django.test import TestCase

from app.common import keys


class KeysLoaderTests(TestCase):
    def test_t_basic_and_format(self):
        keys.ready()
        msg = keys.t('errors.revision.cap_reached', count=3, limit=5)
        self.assertIn('3/5', msg)
        self.assertTrue(msg.startswith("You've reached"))

    def test_missing_key_fallback(self):
        keys.ready()
        sentinel = 'does.not.exist.key'
        self.assertEqual(keys.t(sentinel), sentinel)
