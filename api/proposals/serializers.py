from rest_framework import serializers
from typing import Optional
from orgs.models import Organization
from billing.quota import can_unarchive

from .models import Proposal


class ProposalSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.id")
    can_unarchive = serializers.SerializerMethodField()

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
            "can_unarchive",
            "created_at",
        ]
        read_only_fields = ["last_edited", "downloads", "created_at"]

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
