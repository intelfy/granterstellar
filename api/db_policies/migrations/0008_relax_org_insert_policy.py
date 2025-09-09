from django.db import migrations


SQL = r"""
-- Allow INSERTs on orgs_organization without WITH CHECK constraints; visibility still governed by SELECT policy
DROP POLICY IF EXISTS orgs_insert ON orgs_organization;
CREATE POLICY orgs_insert ON orgs_organization
    FOR INSERT
    WITH CHECK (true);
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0007_adjust_policies_semantics'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
