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
    # Optional grant call URL (immutable once set). Used for template/RAG detection.
    call_url = models.URLField(max_length=800, null=True, blank=True, help_text="Original grant call / funding opportunity URL; write-once.")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"Proposal {self.pk} ({self.state})"

    def save(self, *args, **kwargs):  # pragma: no cover - simple immutability guard
        if self.pk is not None and 'update_fields' in kwargs:
            # If call_url already persisted, prevent changing it.
            if 'call_url' in kwargs['update_fields']:
                orig = Proposal.objects.filter(pk=self.pk).values_list('call_url', flat=True).first()
                if orig and self.call_url != orig:
                    # Revert to original silently to avoid raising in generic update paths.
                    self.call_url = orig
                    # Remove from update_fields to avoid unnecessary write.
                    kwargs['update_fields'] = [f for f in kwargs['update_fields'] if f != 'call_url']
        super().save(*args, **kwargs)


class ProposalSection(models.Model):
    """Structured section of a Proposal for granular AI workflows.

    Evolution Note:
    - Original fields: content (accepted), draft_content (working).
    - Added in alpha planning phase: state, approved_content, revisions.
    The legacy ``content`` field is retained (mirrors approved_content) for
    backward compatibility with existing code paths; future migration can
    consolidate once all callers use ``approved_content``.
    """
    STATE_CHOICES = (
        ("draft", "Draft"),
        ("approved", "Approved"),
    )
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="sections")
    key = models.CharField(max_length=128, db_index=True)
    title = models.CharField(max_length=256, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    # Latest approved/locked text (duplicated from legacy 'content').
    approved_content = models.TextField(blank=True, default="")
    # Legacy field kept for compatibility; will be synced on save() override.
    content = models.TextField(blank=True, default="")  # deprecated alias
    # In-progress AI or user draft.
    draft_content = models.TextField(blank=True, default="")
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="draft")
    # Append-only log of revisions (lightweight JSON list). Each item shape:
    # {"ts": iso8601, "user_id": int|None, "from": str, "to": str, "diff": {...optional structured blocks...}}
    revisions = models.JSONField(default=list, blank=True)
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
            models.Index(fields=["proposal", "state"], name="proposal_section_state_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        pid = getattr(self.proposal, 'id', 'unsaved')
        return f"ProposalSection {pid}:{self.key} ({self.state})"

    def save(self, *args, **kwargs):  # pragma: no cover - logic straightforward
        # Keep legacy 'content' synchronized with approved_content for now.
        if self.approved_content and self.content != self.approved_content:
            self.content = self.approved_content
        super().save(*args, **kwargs)

    # --- Revision Logging -------------------------------------------------
    def append_revision(self, *, user_id: int | None, from_text: str, to_text: str, diff: dict | None = None, change_ratio: float | None = None):
        """Append a revision entry to the JSON log.

        Each entry kept intentionally small; full diff blocks already stored with the job context.
        Shape: {"ts", "user_id", "from", "to", "change_ratio", "blocks"?}
        We only persist blocks if provided AND total serialized length is reasonably small (<30k) to avoid bloat.
        """
        import datetime as _dt
        from django.conf import settings as _settings  # local import to avoid at-import dependency churn

        # --- Revision Cap Enforcement -------------------------------------------------
        # A hard business rule: limit revisions retained (and effectively allowed)
        # per section. Default: 5. Overridable via PROPOSAL_SECTION_REVISION_CAP.
        # If the cap is reached we simply skip appending a new revision. This keeps
        # the method idempotent for callers that don't handle exceptions while
        # still enforcing an upper bound. Returning early avoids unnecessary DB writes.
        try:
            _cap_raw = getattr(_settings, 'PROPOSAL_SECTION_REVISION_CAP', 5)
            revision_cap = int(_cap_raw) if _cap_raw not in (None, '') else 5
            if revision_cap <= 0:
                revision_cap = 5  # sanity fallback
        except Exception:  # pragma: no cover - defensive
            revision_cap = 5
        existing = list(self.revisions or [])
        if len(existing) >= revision_cap:
            return  # silently ignore beyond-cap attempts

        # Build base entry with capped text sizes.
        entry = {
            "ts": _dt.datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "from": (from_text or "")[:15000],
            "to": (to_text or "")[:15000],
        }

        if change_ratio is not None:
            try:  # pragma: no cover - defensive
                entry["change_ratio"] = round(float(change_ratio), 4)
            except Exception:
                pass

        # Optional structured diff blocks (already truncated in caller, but re‑guard here).
        if isinstance(diff, dict):
            blocks = diff.get("blocks")
            if isinstance(blocks, list):
                norm_blocks = []
                for b in blocks[:25]:  # limit count
                    if not isinstance(b, dict):
                        continue
                    before_val = b.get("before", "")
                    after_val = b.get("after", "")
                    # Accept either list-of-lines or string; normalize to string then cap.
                    if isinstance(before_val, list):
                        before_val = "\n".join(x for x in before_val if isinstance(x, str))
                    if isinstance(after_val, list):
                        after_val = "\n".join(x for x in after_val if isinstance(x, str))
                    nb = {
                        "type": b.get("type"),
                        "before": str(before_val)[:1000],
                        "after": str(after_val)[:1000],
                    }
                    if "similarity" in b:
                        nb["similarity"] = b.get("similarity")
                    norm_blocks.append(nb)
                if norm_blocks:
                    entry["blocks"] = norm_blocks

        # Mutate revision log with capped length (last 50 entries kept).
        revs = list(self.revisions or [])
        revs.append(entry)
        if len(revs) > 50:
            revs = revs[-50:]
        self.revisions = revs
        try:  # pragma: no cover - best effort
            self.save(update_fields=["revisions", "updated_at"])
        except Exception:  # Newly created instance or update_fields unsupported
            self.save()
