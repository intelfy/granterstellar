# Generated migration for AIPromptTemplate
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ('ai', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIPromptTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=128)),
                ('version', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                (
                    'role',
                    models.CharField(
                        choices=[
                            ('planner', 'planner'),
                            ('writer', 'writer'),
                            ('reviser', 'reviser'),
                            ('formatter', 'formatter'),
                        ],
                        max_length=16,
                    ),
                ),
                ('template', models.TextField()),
                ('checksum', models.CharField(db_index=True, max_length=64)),
                ('variables', models.JSONField(default=list)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['role', 'active'], name='ai_aiprompt_role_acti_idx')],
            },
        ),
        migrations.AddConstraint(
            model_name='aiprompttemplate',
            constraint=models.UniqueConstraint(fields=('name', 'version'), name='prompt_template_version_unique'),
        ),
    ]
