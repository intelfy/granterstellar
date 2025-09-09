from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Organization, OrgUser, OrgInvite


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email')


class OrgUserSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    # Allow adding by email as an alternative to user_id (write-only)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=False)
    # Make role optional; defaulting handled in the view
    role = serializers.ChoiceField(choices=OrgUser.ROLE_CHOICES, required=False, allow_blank=True)

    class Meta:
        model = OrgUser
        fields = ('user', 'user_id', 'email', 'role')


class OrganizationSerializer(serializers.ModelSerializer):
    admin = UserBriefSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = ('id', 'name', 'description', 'admin', 'created_at')


class OrgInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgInvite
        fields = (
            'id',
            'email',
            'role',
            'token',
            'created_at',
            'accepted_at',
            'revoked_at',
            'expires_at',
        )
        read_only_fields = ('id', 'token', 'created_at', 'accepted_at', 'revoked_at', 'expires_at')
