from django.db import migrations


SQL = r"""
-- JSONB GIN index on proposals content for common path queries
CREATE INDEX IF NOT EXISTS idx_proposals_content_gin ON proposals_proposal USING GIN (content jsonb_path_ops);
-- GIN index on shared_with array (int[])
CREATE INDEX IF NOT EXISTS idx_proposals_shared_with_gin ON proposals_proposal USING GIN (shared_with);
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0001_rls'),
        ('proposals', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
