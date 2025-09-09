from django.db import migrations


SQL = r"""
-- Break recursive policy chain between orgs_organization <-> orgs_orguser by
-- removing orgs_organization references from the OrgUser READ policy.
-- Keep WRITE (ALL) policy for OrgUser to still enforce org-admin checks via orgs_organization.

-- OrgUsers READ: only the row owner (the user themselves) can read their membership rows.
DROP POLICY IF EXISTS orgusers_read ON orgs_orguser;
CREATE POLICY orgusers_read ON orgs_orguser
    FOR SELECT USING (
        user_id = app.current_user_id()
    );
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0004_force_rls'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
