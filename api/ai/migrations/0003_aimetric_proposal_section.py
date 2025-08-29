from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0002_aimetric"),
    ]

    operations = [
        migrations.AddField(
            model_name="aimetric",
            name="proposal_id",
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="aimetric",
            name="section_id",
            field=models.CharField(max_length=128, blank=True, default=""),
        ),
    ]
