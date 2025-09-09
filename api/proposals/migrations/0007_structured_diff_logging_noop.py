from django.db import migrations


class Migration(migrations.Migration):
    """No-op migration documenting adoption of structured diff logging.

    Rationale:
    - Revision logging enhancements (structured diff blocks + change_ratio)
      are stored inside existing JSONField `revisions` on ProposalSection.
    - No schema changes required; this migration marks the application
      boundary for future migrations relying on structured diff metadata.
    """
    dependencies = [
        ("proposals", "0006_proposalsection_extensions"),
    ]

    operations = []
