from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='cancel_at_period_end',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='subscription',
            name='canceled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
