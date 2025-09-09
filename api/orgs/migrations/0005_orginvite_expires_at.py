from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orgs', '0004_orgproposalallocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='orginvite',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
