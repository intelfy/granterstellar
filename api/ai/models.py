from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator


class AIPromptTemplate(models.Model):
    """Versioned prompt template owned by backend (users never edit directly).

    name: machine-readable identifier (e.g., planner.base)
    version: monotonically increasing integer
    role: planner|writer|reviser|formatter (for fast filtering)
    template: raw template text with {{variable}} placeholders
    checksum: sha256 of template text (quick integrity check)
    variables: declared variable names (for validation / rendering safety)
    active: soft flag to allow deprecation while keeping history
    """

    ROLE_CHOICES = [
        ("planner", "planner"),
        ("writer", "writer"),
        ("reviser", "reviser"),
        ("formatter", "formatter"),
    ]

    name = models.CharField(max_length=128, db_index=True)
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    template = models.TextField()
    checksum = models.CharField(max_length=64, db_index=True)
    variables = models.JSONField(default=list)  # list[str]
    active = models.BooleanField(default=True)
    # Optional structural output blueprint (JSON schema-like) for roles that require constrained formatting
    blueprint_schema = models.JSONField(null=True, blank=True)
    # Human authored instructions describing how to conform to blueprint (displayed to provider prompt)
    blueprint_instructions = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name", "version"], name="prompt_template_version_unique"),
        ]
        indexes = [models.Index(fields=["role", "active"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"AIPromptTemplate({self.name}@v{self.version})"

    @staticmethod
    def compute_checksum(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):  # pragma: no cover - simple override
        # Always recompute checksum when template text is being saved (initial create or template field updated)
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "template" in update_fields:
            self.checksum = self.compute_checksum(self.template)
        super().save(*args, **kwargs)


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
    ("promote", "promote"),  # section promotion event
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


class AIJobContext(models.Model):
    """Audit + reproducibility context for an AIJob.

    Stores the rendered (redacted) prompt snapshot, template/version and basic model params
    plus retrieval metadata once retrieval is integrated. Users never see raw unredacted prompt.
    """

    job = models.ForeignKey(AIJob, on_delete=models.CASCADE, related_name="contexts")
    prompt_template = models.ForeignKey(
        AIPromptTemplate, null=True, blank=True, on_delete=models.SET_NULL
    )
    prompt_version = models.PositiveIntegerField(default=1)
    rendered_prompt_redacted = models.TextField()
    model_params = models.JSONField(default=dict)
    snippet_ids = models.JSONField(default=list)
    retrieval_metrics = models.JSONField(default=dict)
    # sha256 of the exact template text (post substitution template, prior to variable injection) for drift detection
    template_sha256 = models.CharField(max_length=64, blank=True, default="")
    # mapping of redacted token -> original classification (not the original literal) for forensic/audit
    redaction_map = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["job"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"AIJobContext(job={getattr(self.job, 'id', 'unsaved')},v={self.prompt_version})"

    @staticmethod
    def redact(text: str) -> str:
        """Backward compatible simple redaction returning string only (deprecated)."""
        redacted, _ = AIJobContext.redact_with_mapping(text)
        return redacted

    @staticmethod
    def redact_with_mapping(text: str) -> tuple[str, dict[str, str]]:
        """Extended deterministic redaction.

        Returns (redacted_text, mapping) where mapping is token->classification (NOT raw value).
        Classifications: EMAIL, NUMBER, PHONE, SIMPLE_NAME, ID_CODE, ADDRESS_LINE
        """
        import re
        import hashlib
        if not text:
            return text, {}
        mapping: dict[str, str] = {}

        patterns: list[tuple[str, str]] = [
            (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "EMAIL"),
            (r"\b\d{6,}\b", "NUMBER"),
            (r"\b\+?[0-9][0-9\-\s]{6,}[0-9]\b", "PHONE"),
            (r"\b[A-Z]{2}[0-9]{2,}\b", "ID_CODE"),  # simplistic code/id pattern
            (r"\b([A-Z][a-z]{1,15}\s[A-Z][a-z]{1,15})\b", "SIMPLE_NAME"),
            (r"\b\d+\s+[A-Z][A-Za-z]+\s+(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln)\b", "ADDRESS_LINE"),
        ]

        def token_for(val: str, cls: str) -> str:
            h = hashlib.sha256(val.encode('utf-8')).hexdigest()[:10]
            return f"[{cls}_{h}]"

        redacted = text
        for pattern, classification in patterns:
            def repl(m, _c=classification):  # bind current classification
                val = m.group(0)
                tok = token_for(val, _c)
                mapping.setdefault(tok, _c)
                return tok
            redacted = re.sub(pattern, repl, redacted)

        if len(redacted) > 20000:
            redacted = redacted[:20000] + "…"
        return redacted, mapping


class AIResource(models.Model):
    """Source document for RAG (template, sample, or call snapshot)."""

    TYPE_CHOICES = [
        ("template", "template"),
        ("sample", "sample"),
        ("call_snapshot", "call_snapshot"),
    ]
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    title = models.CharField(max_length=256, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    sha256 = models.CharField(max_length=64, db_index=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"AIResource({self.type},{self.id})"  # type: ignore[attr-defined]

    @staticmethod
    def compute_sha256(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AIChunk(models.Model):
    """Embedded chunk of an AIResource."""

    resource = models.ForeignKey(AIResource, on_delete=models.CASCADE, related_name="chunks")
    ord = models.IntegerField()
    text = models.TextField()
    token_len = models.IntegerField(default=0)
    embedding_key = models.CharField(max_length=64, blank=True, default="")  # placeholder until vector store integration
    # Cached embedding vector (list[float]) for naive in-DB retrieval; replace with external vector store later
    embedding = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["resource", "ord"], name="aichunk_resource_ord_unique"),
        ]
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["embedding_key"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"AIChunk(res={getattr(self.resource, 'id', 'unsaved')},ord={self.ord})"
