# Generated migration for AIResource and AIChunk
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ai', '0003_aijobcontext'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'type',
                    models.CharField(
                        choices=[('template', 'template'), ('sample', 'sample'), ('call_snapshot', 'call_snapshot')],
                        max_length=32,
                    ),
                ),
                ('title', models.CharField(blank=True, default='', max_length=256)),
                ('source_url', models.URLField(blank=True, default='')),
                ('sha256', models.CharField(db_index=True, max_length=64)),
                ('metadata', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['type'], name='ai_airesour_type_9d1e1c_idx'),
                    models.Index(fields=['created_at'], name='ai_airesour_created__idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AIChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ord', models.IntegerField()),
                ('text', models.TextField()),
                ('token_len', models.IntegerField(default=0)),
                ('embedding_key', models.CharField(blank=True, default='', max_length=64)),
                ('metadata', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'resource',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='ai.airesource'),
                ),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('resource', 'ord'), name='aichunk_resource_ord_unique'),
                ],
                'indexes': [
                    models.Index(fields=['resource'], name='ai_aichunk_resource_id_idx'),
                    models.Index(fields=['embedding_key'], name='ai_aichunk_embedding__idx'),
                ],
            },
        ),
    ]
