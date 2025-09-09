from django.db import migrations


class Migration(migrations.Migration):
    """Merge conflicting migration branches.

    Branch A path: 0001_initial → 0002_aiprompttemplate → 0003_aijobcontext → 0004_airesource_aichunk → 0005_aichunk_embedding
    Branch B path: 0001_initial → 0002_aimetric → 0003_aimetric_proposal_section → 0004_aimemory → 0005_rename_ai_mem_org_section_idx_...

    This merge establishes a single linear continuation for future migrations.
    No schema operations needed because prior migrations already perform required
    changes (field addition + index renames)."""

    dependencies = [
        ('ai', '0005_aichunk_embedding'),
        ('ai', '0005_rename_ai_mem_org_section_idx_ai_aimemory_org_id_c0a075_idx_and_more'),
    ]

    operations = []
