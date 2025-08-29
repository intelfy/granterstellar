import os
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, re_path, include
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from pathlib import Path
from django.conf import settings
from accounts.views import me, DebugTokenObtainPairView
from billing.views import usage, customer_portal, checkout, cancel_subscription, resume_subscription
from billing.webhooks import stripe_webhook
from rest_framework.routers import DefaultRouter
from proposals.views import ProposalViewSet
from orgs.views import OrganizationViewSet, OrgInviteAcceptView
from ai import views as ai_views
from exports import views as export_views
from files import views as files_views
from accounts.oauth import google_start, google_callback, github_start, github_callback, facebook_start, facebook_callback


def healthz(_request):
    return HttpResponse('ok')


router = DefaultRouter()
router.register(r'proposals', ProposalViewSet, basename='proposal')
router.register(r'orgs', OrganizationViewSet, basename='org')

urlpatterns = [
    path('healthz', healthz),
    path('api/me', me),
    # In DEBUG, route password logins through a view that marks the user as Pro tier for testing
    path('api/token', DebugTokenObtainPairView.as_view() if settings.DEBUG else TokenObtainPairView.as_view()),
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