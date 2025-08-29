from django.db import migrations


SQL = r'''
DO $$
BEGIN
    -- Ensure table exists before altering policy
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'proposals_proposal'
    ) THEN
        BEGIN
            -- Drop and recreate with corrected shared_with membership check
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
        EXCEPTION WHEN undefined_object THEN
            -- Ignore if policy/table doesn't exist yet in this environment
            NULL;
        END;
    END IF;
END
$$;
'''


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0001_rls'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
