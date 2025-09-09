from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proposals", "0005_proposalsection"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposalsection",
            name="approved_content",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="proposalsection",
            name="state",
            field=models.CharField(choices=[("draft", "Draft"), ("approved", "Approved")], default="draft", max_length=16),
        ),
        migrations.AddField(
            model_name="proposalsection",
            name="revisions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddIndex(
            model_name="proposalsection",
            index=models.Index(fields=["proposal", "state"], name="proposal_section_state_idx"),
        ),
    ]
