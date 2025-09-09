from django.test import TestCase
from ai.ingestion import create_resource_with_chunks
from ai.retrieval import retrieve_top_k
from ai.models import AIChunk


class IngestionRetrievalTests(TestCase):
    def test_ingestion_stores_embeddings_and_retrieval(self):
        text = 'Paragraph one. Paragraph two with more words. Paragraph three is here.'
        res = create_resource_with_chunks(type_='sample', title='Sample', source_url='', full_text=text)
        chunks = list(res.chunks.all())  # type: ignore[attr-defined]
        self.assertGreaterEqual(len(chunks), 1)
        # All chunks have embedding stored
        for ch in chunks:
            self.assertIsInstance(ch.embedding, list)
            self.assertGreater(len(ch.embedding), 0)
        out = retrieve_top_k('Paragraph two', k=3)
        self.assertGreaterEqual(len(out), 1)
        # Ensure retrieval attaches score and text
        self.assertIn('score', out[0])
        # Ensure no on-demand re-embed left embedding null
        self.assertEqual(AIChunk.objects.filter(embedding__isnull=True).count(), 0)
