from django.test import TestCase
from ai.ingestion import create_resource_with_chunks
from ai.models import AIResource


class IngestionSimilarityDedupeTests(TestCase):
    def test_near_duplicate_reuses_resource(self):
        base = 'This is a simple grant template text about health and education.'
        r1 = create_resource_with_chunks(type_='template', title='T1', source_url='', full_text=base)
        # Slight variation (add a word) should still dedupe at 0.97 threshold
        variant = base + ' Impact.'
        r2 = create_resource_with_chunks(type_='template', title='T2', source_url='', full_text=variant)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(AIResource.objects.filter(type='template').count(), 1)

    def test_different_below_threshold_creates_new(self):
        base = 'Funding science initiatives in rural areas with community outreach.'
        r1 = create_resource_with_chunks(type_='template', title='A', source_url='', full_text=base)
        # Make a sufficiently different text
        different = 'Completely unrelated agricultural policy document focusing on soil management.'  # noqa: E501
        r2 = create_resource_with_chunks(type_='template', title='B', source_url='', full_text=different)
        self.assertNotEqual(r1.id, r2.id)
        self.assertEqual(AIResource.objects.filter(type='template').count(), 2)
