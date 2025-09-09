import os
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, re_path, include
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from pathlib import Path
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from app.errors import error_response
from accounts.views import MeView, DebugTokenObtainPairView, ThrottledTokenObtainPairView
from billing.views import usage, customer_portal, checkout, cancel_subscription, resume_subscription
from billing.webhooks import stripe_webhook
from rest_framework.routers import DefaultRouter
from proposals.views import ProposalViewSet
from proposals.views import SectionPromotionView
from orgs.views import OrganizationViewSet, OrgInviteAcceptView
from ai import views as ai_views
from exports import views as export_views
from files import views as files_views
from accounts.oauth import google_start, google_callback, github_start, github_callback, facebook_start, facebook_callback


def healthz(_request):
    return HttpResponse('ok')


@api_view(['GET'])
@permission_classes([AllowAny])
def api_healthz(_request):
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_health(_request):
    """Lightweight liveness probe (no DB)."""
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_ready(_request):
    """Readiness probe: checks DB and (optionally) cache connectivity.

    Returns shape:
    {"status":"ok|error","db":bool,"cache":bool,"details":{...}}
    """
    db_ok = False
    cache_ok = False
    details = {}
    # DB check
    try:
        from django.db import connections

        with connections['default'].cursor() as cur:  # type: ignore[index]
            cur.execute('SELECT 1')
            cur.fetchone()
        db_ok = True
    except Exception as exc:  # pragma: no cover - defensive
        details['db_error'] = str(exc)[:200]
    # Cache check (only if configured)
    try:
        from django.core.cache import cache

        test_key = 'ready_probe'
        cache.set(test_key, '1', 5)
        val = cache.get(test_key)
        cache_ok = val == '1'
    except Exception as exc:  # pragma: no cover
        details['cache_error'] = str(exc)[:200]
    status = 'ok' if db_ok else 'error'
    payload = {'status': status, 'db': db_ok, 'cache': cache_ok, 'details': details}
    if status == 'error':
        # Wrap in standardized error format while still including top-level keys for backward compatibility.
        err = error_response('ready_check_failed', 'One or more readiness checks failed', status=503, meta=payload)
        return err
    return Response(payload)


router = DefaultRouter()
router.register(r'proposals', ProposalViewSet, basename='proposal')
router.register(r'orgs', OrganizationViewSet, basename='org')

urlpatterns = [
    path('healthz', healthz),
    path('api/healthz', api_healthz),  # legacy simple probe
    path('api/health', api_health),  # lightweight liveness
    path('api/ready', api_ready),  # readiness (db/cache)
    path('api/me', MeView.as_view()),
    # In DEBUG, route password logins through a view that marks the user as Pro tier for testing
    path('api/token', DebugTokenObtainPairView.as_view() if settings.DEBUG else ThrottledTokenObtainPairView.as_view()),
    path('api/token/refresh', TokenRefreshView.as_view()),
    path('api/usage', usage),
    path('api/billing/portal', customer_portal),
    path('api/billing/checkout', checkout),
    path('api/billing/cancel', cancel_subscription),
    path('api/billing/resume', resume_subscription),
    # OAuth (Google)
    path('api/oauth/google/start', google_start),
    path('api/oauth/google/callback', google_callback),
    # OAuth (GitHub)
    path('api/oauth/github/start', github_start),
    path('api/oauth/github/callback', github_callback),
    # OAuth (Facebook)
    path('api/oauth/facebook/start', facebook_start),
    path('api/oauth/facebook/callback', facebook_callback),
    path('api/stripe/webhook', stripe_webhook),
    # Exports
    path('api/exports', export_views.create_export),
    path('api/exports/<int:job_id>', export_views.get_export),
    # Files
    path('api/files', files_views.upload),
    # AI endpoints (stubs)
    path('api/ai/plan', ai_views.plan),
    path('api/ai/write', ai_views.write),
    path('api/ai/revise', ai_views.revise),
    path('api/ai/format', ai_views.format),
    path('api/ai/jobs/<int:job_id>', ai_views.job_status),
    path('api/ai/metrics/recent', ai_views.metrics_recent),
    path('api/ai/metrics/summary', ai_views.metrics_summary),
    path('api/ai/memory/suggestions', ai_views.memory_suggestions),
    # Section promotion (lock/unlock)
    path('api/sections/<str:section_id>/promote', SectionPromotionView.as_view()),
    # Org invites
    path('api/orgs/invites/accept', OrgInviteAcceptView.as_view({'post': 'create'})),
    # Proposals API
    path('api/', include(router.urls)),
    # Landing page at root (bare domain) or redirect to /app for app subdomains
    re_path(r'^$', lambda r: _root_entrypoint(r)),
    # SPA served under /app
    re_path(r'^app/?$', lambda _r: _serve_spa_index()),
    # SPA deep-links: serve index.html so the client router can handle routes under /app/*
    re_path(r'^app/.*$', lambda _r: _serve_spa_index()),
]

if settings.DEBUG or os.getenv('SERVE_MEDIA', '0') == '1':
    # For MVP single-app deployments, optionally let Django serve MEDIA in production
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def _serve_spa_index():
    # Look for built spa index at STATIC_ROOT/app/index.html
    candidate_paths = [
        Path(settings.STATIC_ROOT) / 'app' / 'index.html',
        Path(settings.BASE_DIR) / 'staticfiles' / 'app' / 'index.html',
    ]
    for p in candidate_paths:
        try:
            text = p.read_text(encoding='utf-8')
            return HttpResponse(text, content_type='text/html; charset=utf-8')
        except Exception:
            continue
    return HttpResponse('SPA not built yet. API is up.', content_type='text/plain; charset=utf-8')


def _serve_landing_index():
    candidate_paths = [
        Path(settings.STATIC_ROOT) / 'index.html',
        Path(settings.BASE_DIR) / 'staticfiles' / 'index.html',
    ]
    for p in candidate_paths:
        try:
            text = p.read_text(encoding='utf-8')
            return HttpResponse(text, content_type='text/html; charset=utf-8')
        except Exception:
            continue
    return HttpResponse('Landing not bundled. API is up.', content_type='text/plain; charset=utf-8')


def _root_entrypoint(request):
    """Serve landing on primary domain; redirect app hosts to /app.
    APP_HOSTS is a comma-separated list of hostnames (no scheme) that should default to the SPA.
    Example: APP_HOSTS=app.grants.intelfy.dk,app.forgranted.io
    """
    host = (request.get_host() or '').split(':')[0].lower()
    from django.conf import settings as _s

    if host and getattr(_s, 'APP_HOSTS', None):
        if host in _s.APP_HOSTS:
            return HttpResponseRedirect('/app')
    return _serve_landing_index()
