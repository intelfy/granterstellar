from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from ai.models import AIMemory


@override_settings(DEBUG=True)
class AIMemoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='memuser', password='x')

    def test_record_and_suggest_user_scope(self):
        AIMemory.record(user=self.user, org_id='', section_id='summary', key='objective', value='Improve outcomes')
        AIMemory.record(
            user=self.user, org_id='', section_id='summary', key='objective', value='Improve outcomes'
        )  # duplicate increments
        items = AIMemory.suggestions(user=self.user, org_id='', section_id='summary', limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['key'], 'objective')
        self.assertGreaterEqual(items[0]['usage_count'], 1)

    def test_record_org_scope(self):
        AIMemory.record(user=self.user, org_id='42', section_id='budget', key='total', value='$10k')
        items = AIMemory.suggestions(user=self.user, org_id='42', section_id='budget', limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['key'], 'total')
