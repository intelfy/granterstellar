from django.db import migrations

SQL = r"""
-- Allow org members (not only org admins) to read their org subscription tier.
-- This preserves least-privilege on write operations while enabling accurate UI usage limits.
-- Policy grants SELECT only; existing subscriptions_write remains admin/owner restricted.
DROP POLICY IF EXISTS subscriptions_read_members ON billing_subscription;
CREATE POLICY subscriptions_read_members ON billing_subscription
    FOR SELECT USING (
        app.current_user_id() IS NOT NULL AND
        billing_subscription.owner_org_id IS NOT NULL AND
        EXISTS (
            SELECT 1 FROM orgs_orguser ou
            WHERE ou.org_id = billing_subscription.owner_org_id
              AND ou.user_id = app.current_user_id()
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
        ('db_policies', '0013_merge_resolve_0011_conflict'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
