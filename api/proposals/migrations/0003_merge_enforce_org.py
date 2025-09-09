from django.db import migrations


def noop(apps, schema_editor):
    """Pure merge stub: previously performed enforcement now moved to 0003_require_org_on_proposal.

    This keeps historical merge naming while linearizing the graph (0003_require_org_on_proposal
    depends on this stub). Safe to keep as no-op.
    """
    return


class Migration(migrations.Migration):
    dependencies = [
        ('proposals', '0002_proposal_archived_at'),
        ('proposals', '0002_require_org_on_proposal'),
    ]

    operations = [
        migrations.RunPython(noop, migrations.RunPython.noop),
    ]
