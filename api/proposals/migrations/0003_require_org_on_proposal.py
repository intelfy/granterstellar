from django.db import migrations, models


def backfill_null_org_proposals(apps, schema_editor):
    """Backfill proposals with NULL org by creating a synthetic org per author.

    Rationale: We can't delete rows referenced by other tables (FK constraints).
    Product direction eliminates personal proposals going forward, but existing
    data must remain referentially intact. Each affected author gets one
    'Personal (Migrated)' org used for all their legacy proposals.
    """
    Organization = apps.get_model('orgs', 'Organization')
    User = apps.get_model('auth', 'User')
    Proposal = apps.get_model('proposals', 'Proposal')

    # Collect authors with NULL org proposals
    author_ids = Proposal.objects.filter(org__isnull=True).values_list('author_id', flat=True).distinct()
    for author_id in author_ids:
        try:
            user = User.objects.get(pk=author_id)
        except User.DoesNotExist:  # Orphaned proposals; skip (allow delete via cascade later)
            continue
        org = Organization.objects.create(
            name=f'{user.username} Personal (Migrated)',
            admin_id=user.id,
        )
        Proposal.objects.filter(org__isnull=True, author_id=author_id).update(org_id=org.id)


class Migration(migrations.Migration):
    dependencies = [
        ('proposals', '0003_merge_enforce_org'),
    ]

    operations = [
        migrations.RunPython(backfill_null_org_proposals, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='proposal',
            name='org',
            field=models.ForeignKey(
                to='orgs.organization',
                on_delete=models.SET_NULL,
                null=False,
                blank=False,
                related_name='proposals',
            ),
        ),
    ]
