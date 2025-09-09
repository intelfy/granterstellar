from django.db import migrations, models


class Migration(migrations.Migration):
    # Correct dependency to ensure AIChunk model exists before adding field.
    dependencies = [
        ('ai', '0004_airesource_aichunk'),
    ]

    operations = [
        migrations.AddField(
            model_name='aichunk',
            name='embedding',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
