from django.db import migrations


def backfill_embeddings(apps, schema_editor):
    AIChunk = apps.get_model('ai', 'AIChunk')
    embed_texts = __import__('ai.embedding_service', fromlist=['embed_texts']).embed_texts  # lazy import
    updated = 0
    # Batch for minimal memory. Use small batch size due to deterministic cheap hash.
    BATCH = 100
    qs = AIChunk.objects.filter(embedding__isnull=True).order_by('id')
    start = 0
    total = qs.count()
    while True:
        batch = list(qs[start:start + BATCH])
        if not batch:
            break
        texts = [c.text for c in batch]
        vectors = embed_texts(texts)
        for c, v in zip(batch, vectors):
            c.embedding = v
            c.save(update_fields=['embedding'])
            updated += 1
        start += BATCH
    if updated:
        print(f"Backfilled embeddings for {updated} / {total} AIChunk rows")


def noop_reverse(apps, schema_editor):
    # Irreversible data backfill; leave embeddings in place.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0006_merge_20250908_aischema"),
    ]

    operations = [
        migrations.RunPython(backfill_embeddings, noop_reverse),
    ]
