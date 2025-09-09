from django.db import migrations

SQL = r"""
-- 0011_replace_proposals_policies
-- Security Goals:
-- 1. Remove broad proposals_write policy (FOR ALL) introduced earlier; revert to granular INSERT/UPDATE/DELETE.
-- 2. Enforce that all proposals are org-scoped (org_id required) and writes require BOTH (a) org admin identity (orgs_organization.admin_id) AND (b) current role GUC = 'admin'.
-- 3. Prevent privilege retention after role downgrade: role GUC gate ensures writes denied if role != 'admin'.
-- 5. Preserve read semantics from migration 0010 (no role gate) to avoid unnecessary regressions; reads governed by author/shared_with/org admin (admin_id) logic.
-- 6. Provide Just-In-Time (JIT) permission mechanism guidance: we require table owner context to DROP old policies; if not owner we abort with clear message instead of layering permissive policies (RLS is OR).

-- Implementation Notes:
-- * PostgreSQL requires table owner or superuser to DROP/CREATE POLICY.
-- * This migration checks ownership; if current_user != owner we RAISE EXCEPTION instructing operator to run with the owning role (or temporarily SET ROLE / use a privileged ephemeral role) and re-run.
-- * We avoid attempting insecure workarounds (e.g., additive restrictive policies) because they are ineffective under RLS OR semantics.

DO $outer$
DECLARE
    tbl_reg regclass := 'public.proposals_proposal'::regclass;
    owner_name text;
BEGIN
    SELECT pg_catalog.pg_get_userbyid(relowner) INTO owner_name
    FROM pg_class WHERE oid = tbl_reg;

    IF owner_name IS DISTINCT FROM current_user THEN
        RAISE EXCEPTION USING MESSAGE = format(
            'RLS migration 0011 requires table owner (%%) to execute; current user=%%. Switch to the owning role or grant a JIT elevated role just for this migration.',
            owner_name, current_user
        );
    END IF;

    -- Drop legacy broad or granular policies if they exist
    EXECUTE 'DROP POLICY IF EXISTS proposals_write ON proposals_proposal';
    EXECUTE 'DROP POLICY IF EXISTS proposals_insert ON proposals_proposal';
    EXECUTE 'DROP POLICY IF EXISTS proposals_update ON proposals_proposal';
    EXECUTE 'DROP POLICY IF EXISTS proposals_delete ON proposals_proposal';

    -- Re-create granular policies.
    -- INSERT
    EXECUTE $pol$
        CREATE POLICY proposals_insert ON proposals_proposal
        FOR INSERT
        WITH CHECK (
            app.current_role() = 'admin' AND EXISTS (
                SELECT 1 FROM orgs_organization o
                WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
            )
        );
    $pol$;

    -- UPDATE
    EXECUTE $pol$
        CREATE POLICY proposals_update ON proposals_proposal
        FOR UPDATE
        USING (
            app.current_role() = 'admin' AND EXISTS (
                SELECT 1 FROM orgs_organization o
                WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
            )
        )
        WITH CHECK (
            app.current_role() = 'admin' AND EXISTS (
                SELECT 1 FROM orgs_organization o
                WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
            )
        );
    $pol$;

    -- DELETE
    EXECUTE $pol$
        CREATE POLICY proposals_delete ON proposals_proposal
        FOR DELETE
        USING (
            app.current_role() = 'admin' AND EXISTS (
                SELECT 1 FROM orgs_organization o
                WHERE o.id = proposals_proposal.org_id AND o.admin_id = app.current_user_id()
            )
        );
    $pol$;
END $outer$;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0010_tighten_policies'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
