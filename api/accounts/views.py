from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from billing.models import Subscription


@api_view(["GET"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def me(request):
    user = request.user if request.user and request.user.is_authenticated else None
    data = {
        "authenticated": bool(user),
        "user": {
            "id": getattr(user, 'id', None),
            "username": getattr(user, 'username', None),
            "email": getattr(user, 'email', None),
        } if user else None,
    }
    return Response(data)


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
                sub = (
                    Subscription.objects.filter(owner_user=user)
                    .order_by('-updated_at', '-id')
                    .first()
                )
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
