from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_extracredits_extracredits_extra_owner_present_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='discount',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
