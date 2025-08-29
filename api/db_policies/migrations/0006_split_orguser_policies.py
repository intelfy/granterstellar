from django.db import migrations


SQL = r'''
-- Remove broad FOR ALL policy which referenced orgs_organization and caused recursion on SELECT
DROP POLICY IF EXISTS orgusers_write ON orgs_orguser;

-- Keep the SELECT policy as self-only (created in 0005)

-- Recreate command-specific policies for org membership modifications requiring org admin
-- INSERT: only admins of the target org can add members
DROP POLICY IF EXISTS orgusers_insert ON orgs_orguser;
CREATE POLICY orgusers_insert ON orgs_orguser
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    );

-- UPDATE: only org admins can update membership rows
DROP POLICY IF EXISTS orgusers_update ON orgs_orguser;
CREATE POLICY orgusers_update ON orgs_orguser
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    );

-- DELETE: only org admins can remove members
DROP POLICY IF EXISTS orgusers_delete ON orgs_orguser;
CREATE POLICY orgusers_delete ON orgs_orguser
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    );
'''


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0005_break_recursion_and_lock_orguser_read'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
