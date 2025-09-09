from rest_framework import serializers
from typing import Optional
from orgs.models import Organization
from billing.quota import can_unarchive

from .models import Proposal


class ProposalSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.id")
    can_unarchive = serializers.SerializerMethodField()
    call_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    # Org is assigned server-side (personal org auto-provision or validated membership) – read-only to clients.
    org = serializers.PrimaryKeyRelatedField(read_only=True)
    # Lightweight read-only section listing for UI composition. Avoids
    # embedding large draft/approved texts. Order guaranteed by model Meta.
    sections = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = [
            "id",
            "author",
            "org",
            "state",
            "last_edited",
            "downloads",
            "content",
            "schema_version",
            "shared_with",
            "archived_at",
            "call_url",
            "can_unarchive",
            "created_at",
            "sections",
        ]
    read_only_fields = ["last_edited", "downloads", "created_at", "org"]

    def get_can_unarchive(self, obj: Proposal) -> bool:
        # Only relevant for archived proposals; others return True
        if obj.state != "archived":
            return True
        request = self.context.get("request")
        if not request or not getattr(request, "user", None):
            return False
        org: Optional[Organization] = None
        org_id = request.headers.get("X-Org-ID") if hasattr(request, 'headers') else None
        if org_id and org_id.isdigit():
            org = Organization.objects.filter(id=int(org_id)).first()
        allowed, _details = can_unarchive(request.user, org, obj)
        return bool(allowed)

    def update(self, instance: Proposal, validated_data):
        # Enforce call_url immutability (write-once). If already set, drop any new value.
        if instance.call_url:
            validated_data.pop('call_url', None)
        return super().update(instance, validated_data)

    def get_sections(self, obj: Proposal):  # pragma: no cover - simple serialization
        try:
            # Access related manager; mypy/ruff (typing) may not see dynamic related_name
            qs = getattr(obj, 'sections', []).all()  # type: ignore[attr-defined]
            from django.conf import settings as _settings
            try:
                _cap_raw = getattr(_settings, 'PROPOSAL_SECTION_REVISION_CAP', 5)
                revision_cap = int(_cap_raw) if _cap_raw not in (None, '') else 5
                if revision_cap <= 0:
                    revision_cap = 5
            except Exception:
                revision_cap = 5
            return [
                {
                    "id": s.id,
                    "key": s.key,
                    "title": s.title,
                    "order": s.order,
                    "state": s.state,
                    "remaining_revision_slots": max(revision_cap - len(getattr(s, 'revisions', []) or []), 0),
                }
                for s in qs
            ]
        except Exception:
            return []
