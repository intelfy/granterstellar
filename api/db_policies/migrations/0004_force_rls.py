from django.db import migrations


SQL = r'''
-- Ensure RLS is enforced even for table owners (Django connections often use owner)
ALTER TABLE IF EXISTS orgs_organization FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS orgs_orguser FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS proposals_proposal FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS billing_subscription FORCE ROW LEVEL SECURITY;
'''


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0003_merge'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
