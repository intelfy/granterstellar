from django.test import TestCase
from ai.ingestion import create_resource_with_chunks
from ai.models import AIResource
from ai.retrieval import retrieve_top_k
from ai.embedding_service import EmbeddingService


class IngestionRetrievalDedupeTests(TestCase):
    def test_duplicate_resource_skipped(self):
        text = 'Alpha beta gamma. Delta epsilon zeta.' * 5
        r1 = create_resource_with_chunks(type_='sample', title='Sample', source_url='', full_text=text)
        r2 = create_resource_with_chunks(type_='sample', title='Sample 2', source_url='', full_text=text)
        # Dedup should return first resource again
        self.assertEqual(r1.id, r2.id)  # type: ignore[attr-defined]
        self.assertEqual(AIResource.objects.filter(type='sample').count(), 1)

    def test_retrieval_deterministic_ordering(self):
        # create two simple resources differing slightly
        base = 'One two three.' * 10
        create_resource_with_chunks(type_='sample', title='R1', source_url='', full_text=base)
        create_resource_with_chunks(type_='sample', title='R2', source_url='', full_text=base + ' extra')
        results_first = retrieve_top_k('one two three', k=5)
        results_second = retrieve_top_k('one two three', k=5)
        self.assertEqual([r['chunk_id'] for r in results_first], [r['chunk_id'] for r in results_second])

    def test_embedding_health(self):
        health = EmbeddingService.instance().health()
        self.assertIn(health['backend'], {'hash', 'minilm'})
        self.assertTrue(health['dim'] in {32, 384})
        self.assertTrue(health['ready'])  # hash backend always ready
