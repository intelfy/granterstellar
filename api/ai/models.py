from django.db import models
from django.contrib.auth import get_user_model


class AIJob(models.Model):
    TYPE_CHOICES = [
        ("plan", "plan"),
        ("write", "write"),
        ("revise", "revise"),
        ("format", "format"),
    ]
    STATUS_CHOICES = [
        ("queued", "queued"),
        ("processing", "processing"),
        ("done", "done"),
        ("error", "error"),
    ]

    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    input_json = models.JSONField(default=dict)
    result_json = models.JSONField(null=True, blank=True)
    error_text = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    org_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        # id attribute available at runtime; ignore static checker
        return f"AIJob#{getattr(self, 'id', 'unsaved')} {self.type} {self.status}"  # type: ignore[attr-defined]


class AIMetric(models.Model):
    TYPE_CHOICES = [
        ("plan", "plan"),
        ("write", "write"),
        ("revise", "revise"),
        ("format", "format"),
    ]

    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    model_id = models.CharField(max_length=64, blank=True, default="")
    # Optional linkage for pricing/analytics
    proposal_id = models.IntegerField(null=True, blank=True)
    section_id = models.CharField(max_length=128, blank=True, default="")
    duration_ms = models.IntegerField(default=0)
    tokens_used = models.IntegerField(default=0)
    success = models.BooleanField(default=True)
    error_text = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        get_user_model(), null=True, blank=True, on_delete=models.SET_NULL
    )
    org_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"AIMetric({self.type},{self.model_id},{self.duration_ms}ms)"


class AIMemory(models.Model):
    """Reusable small snippets of user/org knowledge captured from answers.

    Scope rules:
      - If org_id set: shared across org members (org-scoped memory)
      - Else: user only (personal memory)
    Deduplication:
      - (created_by, org_id, key_hash, value_hash) uniqueness to avoid bloat
    Retrieval:
      - Filter by user/org, optional section_id or key prefix search.
    """

    created_by = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    org_id = models.CharField(max_length=64, blank=True, default="")
    section_id = models.CharField(max_length=128, blank=True, default="")
    key = models.CharField(max_length=256)
    value = models.TextField()
    # Simple hashes for fast dedup (sha256 hex truncated)
    key_hash = models.CharField(max_length=32, db_index=True)
    value_hash = models.CharField(max_length=32, db_index=True)
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "org_id", "key_hash", "value_hash"],
                name="aimemory_dedup_unique",
            )
        ]
        indexes = [
            models.Index(fields=["org_id", "section_id"]),
            models.Index(fields=["created_by", "section_id"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        scope = self.org_id or f"user:{getattr(self.created_by, 'id', 'anon')}"
        return f"AIMemory[{scope}] {self.key[:40]}={self.value[:40]}..."

    @staticmethod
    def hash_text(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    @classmethod
    def record(cls, *, user, org_id: str, section_id: str, key: str, value: str) -> "AIMemory":
        """Idempotently store a key/value memory item and return it.

        Increments usage_count if already present.
        """
        key = (key or "").strip()
        value = (value or "").strip()
        if not key or not value:
            raise ValueError("key and value required")
        kh = cls.hash_text(key)
        vh = cls.hash_text(value)
        obj, created = cls.objects.get_or_create(
            created_by=user if getattr(user, 'is_authenticated', False) else None,
            org_id=org_id or "",
            key_hash=kh,
            value_hash=vh,
            defaults={
                "section_id": section_id or "",
                "key": key[:256],
                "value": value[:2000],  # safety cap
            },
        )
        if not created:
            cls.objects.filter(id=getattr(obj, 'id', None)).update(  # type: ignore[attr-defined]
                usage_count=models.F("usage_count") + 1,
                updated_at=models.functions.Now(),
            )
            obj.usage_count += 1
        return obj

    @classmethod
    def suggestions(cls, *, user, org_id: str, section_id: str | None = None, limit: int = 5):
        qs = cls.objects.all().order_by("-usage_count", "-updated_at")
        if org_id:
            qs = qs.filter(org_id=org_id)
        else:
            # Personal scope: only records explicitly stored without an org_id.
            # We intentionally exclude org-scoped memories even if created_by matches
            # to ensure isolation unless the caller supplies the org header.
            qs = qs.filter(created_by=user, org_id="")
        if section_id:
            qs = qs.filter(section_id=section_id)
        return list(qs.values("key", "value", "usage_count")[:max(1, min(limit, 20))])
