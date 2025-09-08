from django.db import migrations


def noop(apps, schema_editor):
    """Legacy 0011 placeholder retained only to merge branch history.
    The real secure policy replacement lives in 0011_replace_proposals_policies.
    This migration performs no changes so that Django migration graph can linearize.
    """
    return


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0011_replace_proposals_policies'),
    ]

    operations = [
        migrations.RunPython(noop, migrations.RunPython.noop),
    ]
