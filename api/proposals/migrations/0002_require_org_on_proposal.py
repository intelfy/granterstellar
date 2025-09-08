from django.db import migrations


def noop(apps, schema_editor):  # Pure placeholder to satisfy historical merge
    """No-op: original attempt to enforce org non-null replaced by later merge.

    This file exists only to resolve a ghost migration reference so that
    0003_merge_enforce_org can linearize the graph without manual state edits.
    """
    return


class Migration(migrations.Migration):
    dependencies = [
        ("proposals", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(noop, migrations.RunPython.noop),
    ]
