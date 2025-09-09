from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'type',
                    models.CharField(
                        choices=[('plan', 'plan'), ('write', 'write'), ('revise', 'revise'), ('format', 'format')], max_length=16
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[('queued', 'queued'), ('processing', 'processing'), ('done', 'done'), ('error', 'error')],
                        default='queued',
                        max_length=16,
                    ),
                ),
                ('input_json', models.JSONField(default=dict)),
                ('result_json', models.JSONField(blank=True, null=True)),
                ('error_text', models.TextField(blank=True, default='')),
                ('org_id', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
    ]
