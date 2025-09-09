from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from django.db import IntegrityError
from billing.models import Subscription


class MeView(APIView):
    """Authenticated user info and profile update.

    GET: returns auth status and a brief user object. In DEBUG, allows anonymous (for SPA bootstrapping).
    PATCH: updates selected profile fields for the authenticated user (always requires auth).
    """

    def get_permissions(self):  # method-specific permissions
        if self.request.method == 'GET' and settings.DEBUG:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
        data = {
            'authenticated': bool(user),
            'user': {
                'id': getattr(user, 'id', None),
                'username': getattr(user, 'username', None),
                'email': getattr(user, 'email', None),
            }
            if user
            else None,
        }
        return Response(data)

    def patch(self, request):  # profile update
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}
        # Allowed fields only
        allowed = {k: v for k, v in payload.items() if k in {'username', 'email', 'first_name', 'last_name'}}
        if not allowed:
            return Response({'error': 'no_changes'}, status=status.HTTP_400_BAD_REQUEST)

        # Basic validations
        username = allowed.get('username')
        email = allowed.get('email')
        if username is not None:
            username = str(username).strip()
            if not username:
                return Response({'error': 'invalid_username'}, status=400)
            allowed['username'] = username
        if email is not None:
            email = str(email).strip().lower()
            # Minimal email sanity check; model may not enforce uniqueness
            if email and ('@' not in email or '.' not in email.split('@')[-1]):
                return Response({'error': 'invalid_email'}, status=400)
            allowed['email'] = email

        # Apply updates
        for field, value in allowed.items():
            setattr(user, field, value)
        try:
            user.save(update_fields=list(allowed.keys()))
        except IntegrityError:
            return Response({'error': 'username_taken'}, status=400)

        return Response(
            {
                'authenticated': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
            }
        )


class DebugTokenObtainPairView(APIView):
    """DEBUG-only: issue JWTs like TokenObtainPair and upsert a Pro subscription for the user.

    This lets devs test Pro-tier behavior with username/password logins.
    In non-DEBUG environments, do not use this view.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Ensure a Pro subscription exists for this user in DEBUG for testing quotas
        if settings.DEBUG:
            user = getattr(serializer, 'user', None)
            if user is not None:
                sub = Subscription.objects.filter(owner_user=user).order_by('-updated_at', '-id').first()
                if not sub:
                    sub = Subscription(owner_user=user)
                sub.tier = 'pro'
                sub.status = 'active'
                sub.cancel_at_period_end = False
                sub.save()
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """JWT obtain pair view with scoped throttling to deter brute-force attempts."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'
