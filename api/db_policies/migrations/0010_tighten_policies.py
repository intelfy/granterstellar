from django.db import migrations

SQL = r'''
-- Tighten RLS policies: ensure anonymous sessions (no current_user_id) see nothing;
-- block member-level writes unless admin role/org matches; narrow proposal visibility.

-- Proposals: replace read/write policies with stricter versions
DROP POLICY IF EXISTS proposals_read ON proposals_proposal;
CREATE POLICY proposals_read ON proposals_proposal
    FOR SELECT USING (
        app.current_user_id() IS NOT NULL AND (
            author_id = app.current_user_id()
            OR (app.current_user_id() IS NOT NULL AND shared_with @> to_jsonb(ARRAY[app.current_user_id()]))
            OR (
                org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
                )
            )
        )
    );

DROP POLICY IF EXISTS proposals_write ON proposals_proposal;
CREATE POLICY proposals_write ON proposals_proposal
    FOR ALL USING (
        app.current_user_id() IS NOT NULL AND (
            author_id = app.current_user_id()
            OR (
                org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
                )
            )
        )
    ) WITH CHECK (
        app.current_user_id() IS NOT NULL AND (
            author_id = app.current_user_id()
            OR (
                org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
                )
            )
        )
    );

-- Organizations: ensure anon blocked
DROP POLICY IF EXISTS orgs_read ON orgs_organization;
CREATE POLICY orgs_read ON orgs_organization
    FOR SELECT USING (
        app.current_user_id() IS NOT NULL AND (
            admin_id = app.current_user_id() OR EXISTS (
                SELECT 1 FROM orgs_orguser ou
                WHERE ou.org_id = orgs_organization.id AND ou.user_id = app.current_user_id()
            )
        )
    );

DROP POLICY IF EXISTS orgs_write ON orgs_organization;
CREATE POLICY orgs_write ON orgs_organization
    FOR UPDATE USING (
        app.current_user_id() IS NOT NULL AND admin_id = app.current_user_id()
    );

-- Subscriptions: tighten read/write (must own personally or be org admin)
DROP POLICY IF EXISTS subscriptions_read ON billing_subscription;
CREATE POLICY subscriptions_read ON billing_subscription
    FOR SELECT USING (
        app.current_user_id() IS NOT NULL AND (
            (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id()) OR (
                owner_org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
                )
            )
        )
    );

DROP POLICY IF EXISTS subscriptions_write ON billing_subscription;
CREATE POLICY subscriptions_write ON billing_subscription
    FOR ALL USING (
        app.current_user_id() IS NOT NULL AND (
            (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id()) OR (
                owner_org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
                )
            )
        )
    ) WITH CHECK (
        app.current_user_id() IS NOT NULL AND (
            (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id()) OR (
                owner_org_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orgs_organization o
                    WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
                )
            )
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
        ('db_policies', '0009_adjust_orguser_policies_with_role_guc'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
