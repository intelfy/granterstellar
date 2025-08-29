from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_subscription_cancel_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='seats',
            field=models.IntegerField(default=0),
        ),
    ]
