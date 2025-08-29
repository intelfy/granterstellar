from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposal",
            name="archived_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
