from django.db import migrations


SQL = r"""
-- Adjust OrgUser policies to also allow actions when current session role is admin for the target org
DROP POLICY IF EXISTS orgusers_insert ON orgs_orguser;
CREATE POLICY orgusers_insert ON orgs_orguser
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
        OR (
            app.current_role() = 'admin' AND app.current_org_id() = orgs_orguser.org_id
        )
    );

DROP POLICY IF EXISTS orgusers_update ON orgs_orguser;
CREATE POLICY orgusers_update ON orgs_orguser
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
        OR (
            app.current_role() = 'admin' AND app.current_org_id() = orgs_orguser.org_id
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
        OR (
            app.current_role() = 'admin' AND app.current_org_id() = orgs_orguser.org_id
        )
    );

DROP POLICY IF EXISTS orgusers_delete ON orgs_orguser;
CREATE POLICY orgusers_delete ON orgs_orguser
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
        OR (
            app.current_role() = 'admin' AND app.current_org_id() = orgs_orguser.org_id
        )
    );
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0008_relax_org_insert_policy'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
