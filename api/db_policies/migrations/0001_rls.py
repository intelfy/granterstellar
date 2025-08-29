from django.db import migrations


RLS_SQL = r'''
-- Create a dedicated schema for app variables
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
        EXECUTE 'CREATE SCHEMA app';
    END IF;
END $$;

-- Helper functions to read GUCs as integers/text
CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS integer AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_user_id', true), '')::integer;
END; $$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION app.current_org_id() RETURNS integer AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_org_id', true), '')::integer;
END; $$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION app.current_role() RETURNS text AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_role', true), '');
END; $$ LANGUAGE plpgsql STABLE;

-- Ensure RLS is enabled on target tables
ALTER TABLE IF EXISTS orgs_organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS orgs_orguser ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS proposals_proposal ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS billing_subscription ENABLE ROW LEVEL SECURITY;

-- Organizations policies
DROP POLICY IF EXISTS orgs_read ON orgs_organization;
CREATE POLICY orgs_read ON orgs_organization
    FOR SELECT USING (
        -- admin can read their org
        admin_id = app.current_user_id()
        OR EXISTS (
            SELECT 1 FROM orgs_orguser ou
            WHERE ou.org_id = orgs_organization.id AND ou.user_id = app.current_user_id()
        )
    );

DROP POLICY IF EXISTS orgs_write ON orgs_organization;
CREATE POLICY orgs_write ON orgs_organization
    FOR UPDATE USING (
        admin_id = app.current_user_id()
    );

-- OrgUsers policies
DROP POLICY IF EXISTS orgusers_read ON orgs_orguser;
CREATE POLICY orgusers_read ON orgs_orguser
    FOR SELECT USING (
        user_id = app.current_user_id()
        OR EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    );

DROP POLICY IF EXISTS orgusers_write ON orgs_orguser;
CREATE POLICY orgusers_write ON orgs_orguser
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = orgs_orguser.org_id AND o.admin_id = app.current_user_id()
        )
    );

-- Proposals policies
DROP POLICY IF EXISTS proposals_read ON proposals_proposal;
CREATE POLICY proposals_read ON proposals_proposal
    FOR SELECT USING (
        -- creator
        author_id = app.current_user_id()
        -- shared explicitly via shared_with array of user IDs
        OR (app.current_user_id() IS NOT NULL AND shared_with @> to_jsonb(ARRAY[app.current_user_id()]))
        -- org admin access when org present
        OR (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    );

DROP POLICY IF EXISTS proposals_write ON proposals_proposal;
CREATE POLICY proposals_write ON proposals_proposal
    FOR ALL USING (
        author_id = app.current_user_id()
        OR (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    ) WITH CHECK (
        author_id = app.current_user_id()
        OR (org_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM orgs_organization o WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
        ))
    );

-- Subscriptions policies (owner user or org admin)
DROP POLICY IF EXISTS subscriptions_read ON billing_subscription;
CREATE POLICY subscriptions_read ON billing_subscription
    FOR SELECT USING (
        (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id())
        OR (
            owner_org_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM orgs_organization o WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
            )
        )
    );

DROP POLICY IF EXISTS subscriptions_write ON billing_subscription;
CREATE POLICY subscriptions_write ON billing_subscription
    FOR ALL USING (
        (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id())
        OR (
            owner_org_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM orgs_organization o WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
            )
        )
    ) WITH CHECK (
        (owner_user_id IS NOT NULL AND owner_user_id = app.current_user_id())
        OR (
            owner_org_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM orgs_organization o WHERE o.id = billing_subscription.owner_org_id AND o.admin_id = app.current_user_id()
            )
        )
    );
'''


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(RLS_SQL)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('orgs', '0001_initial'),
        ('proposals', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
