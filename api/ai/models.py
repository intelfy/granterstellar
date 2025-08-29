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
        return f"AIJob#{self.id} {self.type} {self.status}"


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
