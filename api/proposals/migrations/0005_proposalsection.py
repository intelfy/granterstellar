from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('proposals', '0004_alter_proposal_org'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProposalSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=128, db_index=True)),
                ('title', models.CharField(max_length=256, blank=True, default='')),
                ('order', models.PositiveIntegerField(default=0)),
                ('content', models.TextField(blank=True, default='')),
                ('draft_content', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('locked', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'proposal',
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='sections', to='proposals.proposal'),
                ),
            ],
            options={
                'ordering': ['proposal_id', 'order', 'id'],
                'unique_together': (('proposal', 'key'),),
                'indexes': [
                    models.Index(fields=['proposal', 'key'], name='proposal_section_key_idx'),
                    models.Index(fields=['proposal', 'order'], name='proposal_section_order_idx'),
                ],
            },
        ),
    ]
