from django.db import migrations


SQL = r'''
-- Organizations: allow creating/deleting by admin (current user must match admin_id)
DROP POLICY IF EXISTS orgs_insert ON orgs_organization;
CREATE POLICY orgs_insert ON orgs_organization
    FOR INSERT
    WITH CHECK (
        admin_id = app.current_user_id()
    );

DROP POLICY IF EXISTS orgs_delete ON orgs_organization;
CREATE POLICY orgs_delete ON orgs_organization
    FOR DELETE
    USING (
        admin_id = app.current_user_id()
    );

-- Proposals: tighten write rules per semantics
-- Remove broad FOR ALL policy
DROP POLICY IF EXISTS proposals_write ON proposals_proposal;

-- INSERT: personal (no org) only by author; org-scoped only by org admin
DROP POLICY IF EXISTS proposals_insert ON proposals_proposal;
CREATE POLICY proposals_insert ON proposals_proposal
    FOR INSERT
    WITH CHECK (
        (org_id IS NULL AND author_id = app.current_user_id()) OR
        (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    );

-- UPDATE: personal only by author; org-scoped only by org admin
DROP POLICY IF EXISTS proposals_update ON proposals_proposal;
CREATE POLICY proposals_update ON proposals_proposal
    FOR UPDATE
    USING (
        (org_id IS NULL AND author_id = app.current_user_id()) OR
        (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    )
    WITH CHECK (
        (org_id IS NULL AND author_id = app.current_user_id()) OR
        (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    );

-- DELETE: personal only by author; org-scoped only by org admin
DROP POLICY IF EXISTS proposals_delete ON proposals_proposal;
CREATE POLICY proposals_delete ON proposals_proposal
    FOR DELETE
    USING (
        (org_id IS NULL AND author_id = app.current_user_id()) OR
        (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    );
'''


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0006_split_orguser_policies'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
