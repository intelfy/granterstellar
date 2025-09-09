from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proposals", "0007_structured_diff_logging_noop"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposal",
            name="call_url",
            field=models.URLField(
                blank=True,
                help_text="Original grant call / funding opportunity URL; write-once.",
                max_length=800,
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="proposal",
            index=models.Index(fields=["call_url"], name="proposal_call_url_idx"),
        ),
    ]
