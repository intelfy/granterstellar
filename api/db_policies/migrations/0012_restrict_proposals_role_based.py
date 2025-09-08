from django.db import migrations


def noop(apps, schema_editor):
    """Renamed legacy placeholder (originally 0011). No-op for graph continuity."""
    return


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0011_replace_proposals_policies'),
    ]

    operations = [
        migrations.RunPython(noop, migrations.RunPython.noop),
    ]
