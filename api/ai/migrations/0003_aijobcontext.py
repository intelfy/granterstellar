# Generated migration for AIJobContext
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0002_aiprompttemplate'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIJobContext',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt_version', models.PositiveIntegerField(default=1)),
                ('rendered_prompt_redacted', models.TextField()),
                ('model_params', models.JSONField(default=dict)),
                ('snippet_ids', models.JSONField(default=list)),
                ('retrieval_metrics', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contexts', to='ai.aijob')),
                ('prompt_template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ai.aiprompttemplate')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['created_at'], name='ai_aijobcon_created__idx'),
                    models.Index(fields=['job'], name='ai_aijobcon_job_id_idx'),
                ],
            },
        ),
    ]
