from django.conf import settings
from django.db import models


class Proposal(models.Model):
    STATE_CHOICES = (
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('archived', 'Archived'),
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proposals')
    org = models.ForeignKey(
        'orgs.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
