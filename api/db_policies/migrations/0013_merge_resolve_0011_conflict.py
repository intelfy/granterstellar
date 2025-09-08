from django.db import migrations


class Migration(migrations.Migration):
    """Merge migration to collapse parallel 0011/0012 placeholder branches.

    No operations; ensures a single linear head for subsequent migrations.
    """

    dependencies = [
        ('db_policies', '0011_replace_proposals_policies'),
        ('db_policies', '0011_restrict_proposals_role_based'),
        ('db_policies', '0012_restrict_proposals_role_based'),
    ]

    operations = []
