from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ai', '0003_aimetric_proposal_section'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('org_id', models.CharField(blank=True, default='', max_length=64)),
                ('section_id', models.CharField(blank=True, default='', max_length=128)),
                ('key', models.CharField(max_length=256)),
                ('value', models.TextField()),
                ('key_hash', models.CharField(max_length=32, db_index=True)),
                ('value_hash', models.CharField(max_length=32, db_index=True)),
                ('usage_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name='aimemory',
            constraint=models.UniqueConstraint(
                fields=['created_by', 'org_id', 'key_hash', 'value_hash'], name='aimemory_dedup_unique'
            ),
        ),
        migrations.AddIndex(
            model_name='aimemory',
            index=models.Index(fields=['org_id', 'section_id'], name='ai_mem_org_section_idx'),
        ),
        migrations.AddIndex(
            model_name='aimemory',
            index=models.Index(fields=['created_by', 'section_id'], name='ai_mem_user_section_idx'),
        ),
    ]
