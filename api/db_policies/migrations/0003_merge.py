from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('db_policies', '0002_fix_proposals_read_policy'),
        ('db_policies', '0002_indexes'),
    ]

    operations = []
