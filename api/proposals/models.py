from django.conf import settings
from django.db import models


class Proposal(models.Model):
    STATE_CHOICES = (
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('archived', 'Archived'),
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proposals')
    # NOTE: Field is NOT NULL (enforced via migration 0003_require_org_on_proposal).
    # Using PROTECT reflects actual expectation: organizations with proposals
    # shouldn't be deleted silently. Historical NULL backfill already occurred.
    # This introduces a small schema divergence (was SET_NULL when nullable).
    # If prior state must be preserved, revert and allow null=True; otherwise
    # generate a migration to align DB constraint with PROTECT.
    org = models.ForeignKey(
        'orgs.Organization',
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name='proposals',
    )
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default='draft')
    last_edited = models.DateTimeField(auto_now=True)
    downloads = models.IntegerField(default=0)
    content = models.JSONField(default=dict)
    schema_version = models.CharField(max_length=16, default='v1')
    shared_with = models.JSONField(default=list, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"Proposal {self.pk} ({self.state})"


class ProposalSection(models.Model):
    """Structured section of a Proposal for granular AI workflows.

    Granularity: Each logical prompt target (e.g., 'impact', 'budget') becomes a
    section enabling independent planning/writing/revision cycles and metrics.
    """
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="sections")
    key = models.CharField(max_length=128, db_index=True)
    title = models.CharField(max_length=256, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    content = models.TextField(blank=True, default="")  # latest accepted text
    draft_content = models.TextField(blank=True, default="")  # in-progress edits
    metadata = models.JSONField(default=dict, blank=True)
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("proposal", "key")
        ordering = ["proposal_id", "order", "id"]
        indexes = [
            models.Index(fields=["proposal", "key"], name="proposal_section_key_idx"),
            models.Index(fields=["proposal", "order"], name="proposal_section_order_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        pid = getattr(self.proposal, 'id', 'unsaved')
        return f"ProposalSection {pid}:{self.key}"
