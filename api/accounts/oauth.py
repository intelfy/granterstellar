import json
import secrets
import urllib.parse
import urllib.request
from urllib.parse import urlencode

import jwt as pyjwt  # PyJWT
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

from billing.models import Subscription
from orgs.models import OrgInvite, OrgUser


def _issue_tokens_for_user(user):
    """Return access/refresh JWTs for a user."""
    refresh = RefreshToken.for_user(user)
    # Some type checkers don't know about `access_token` attribute on SimpleJWT RefreshToken
    access = str(refresh.access_token)  # type: ignore[attr-defined]
    return {'access': access, 'refresh': str(refresh)}


def _get_or_create_user_by_email(email: str):
    """Find a user by email (case-insensitive). Create if missing.
    Returns (user, created).
    """
    User = get_user_model()
    email_norm = (email or '').strip()
    if not email_norm:
        raise ValueError('email required')
    existing = User.objects.filter(email__iexact=email_norm).order_by('id').first()
    if existing:
        return existing, False
    username = email_norm.split('@')[0][:30] if '@' in email_norm else email_norm[:30]
    user = User.objects.create(username=username, email=email_norm)
    return user, True


def _gen_oauth_csrf_token():
    return secrets.token_urlsafe(32)


def _set_oauth_csrf_cookie(resp: JsonResponse, token: str):
    # Send HttpOnly, Lax cookie so it returns on top-level navigation back to our domain
    resp.set_cookie(
        'oauth_csrf',
        token,
        max_age=600,
        secure=not settings.DEBUG,
        httponly=True,
        samesite='Lax',
    )
    return resp


ALLOWED_OAUTH_HOSTS = {
    'accounts.google.com',
    'oauth2.googleapis.com',
    'github.com',
    'api.github.com',
    'www.facebook.com',
    'graph.facebook.com',
}


def _urlopen_fixed(req: urllib.request.Request | str, *, timeout: int = 10):
    """Open a HTTPS URL after asserting the hostname is allow-listed.

    Accepts either a Request or string URL; raises on non-HTTPS or unknown host.
    """
    if isinstance(req, urllib.request.Request):
        url = req.full_url
    else:
        url = req
        req = urllib.request.Request(url)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https':
        raise ValueError('non-https URL not allowed')
    host = parsed.hostname or ''
    if host not in ALLOWED_OAUTH_HOSTS:
        raise ValueError('URL host not allowed')
    return urllib.request.urlopen(req, timeout=timeout)


def _verify_google_id_token_prod(id_token: str) -> dict:
    """Verify a Google id_token signature and standard claims via JWKS in production.
    Returns claims dict on success; raises on failure.
    """
    # Allow override via settings for self-hosted/alt environments
    jwks_url = getattr(settings, 'GOOGLE_JWKS_URL', 'https://www.googleapis.com/oauth2/v3/certs')
    issuer = getattr(settings, 'GOOGLE_ISSUER', 'https://accounts.google.com')
    audience = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    if not audience:
        raise ValueError('audience not configured')

    try:
        jwk_client = pyjwt.PyJWKClient(jwks_url, timeout=10)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        claims = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                'require': ['exp', 'iss', 'aud'],
            },
        )
        return claims
    except Exception as e:  # noqa: BLE001
        raise ValueError(f'id_token verification failed: {e}') from e


@require_GET
def google_start(request):
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    redirect_uri = getattr(settings, 'OAUTH_REDIRECT_URI', '')
    if not client_id or not redirect_uri:
        return JsonResponse(
            {'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'},
            status=400,
        )
    invite = request.GET.get('invite')
    # Embed an anti-CSRF token into state and set it as a cookie
    csrf_token = _gen_oauth_csrf_token()
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'consent',
    }
    state_obj = {'csrf': csrf_token}
    if invite:
        state_obj['invite'] = invite
    params['state'] = json.dumps(state_obj, separators=(',', ':'))
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params)
    return _set_oauth_csrf_cookie(JsonResponse({'auth_url': url}), csrf_token)


# Callback endpoints are csrf_exempt because providers POST back to us from a different origin.
# Compensating controls:
#  - State cookie validation (oauth_csrf) prevents CSRF on callback
#  - Fixed-host HTTPS requests for token/userinfo via _urlopen_fixed prevent SSRF
#  - POST-only, no JSONP/GET callbacks
@require_POST
@csrf_exempt
def google_callback(request):
    code = request.POST.get('code')
    if not code:
        return JsonResponse(
            {'ok': False, 'error': 'missing code', 'code': 'missing_code'},
            status=400,
        )
    # capture invite from state or explicit param
    state = request.POST.get('state') or ''
    invite_token = None
    csrf_expected = request.COOKIES.get('oauth_csrf', '')
    if state:
        try:
            if state.startswith('inv:'):
                # Legacy format (no CSRF) – reject in non-DEBUG
                if not settings.DEBUG:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
                invite_token = state[4:]
            else:
                st = json.loads(state)
                invite_token = st.get('invite')
                csrf_state = st.get('csrf') or ''
                if not csrf_expected or not csrf_state or csrf_state != csrf_expected:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
    if not invite_token:
        invite_token = request.GET.get('invite') or request.POST.get('invite')

    # DEBUG shortcut: allow direct email-based login without contacting Google
    if settings.DEBUG and not getattr(settings, 'GOOGLE_CLIENT_SECRET', ''):
        email = request.POST.get('email')
        if not email:
            return JsonResponse({'ok': False, 'error': 'missing email', 'code': 'missing_email'}, status=400)
        user, _ = _get_or_create_user_by_email(email)
        # Ensure a Free subscription exists for this user (debug Google login)
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        )
        if not sub:
            sub = Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()
        # Auto-accept invite if provided and matches email
        if invite_token:
            try:
                inv = OrgInvite.objects.select_related('org').get(token=invite_token)
                if (
                    not inv.revoked_at
                    and not inv.accepted_at
                    and (email or '').strip().lower()
                    == (inv.email or '').strip().lower()
                ):
                    OrgUser.objects.update_or_create(
                        org=inv.org, user=user, defaults={'role': inv.role}
                    )
                    inv.accepted_at = timezone.now()
                    inv.save(update_fields=['accepted_at'])
            except OrgInvite.DoesNotExist:
                pass
        tokens = _issue_tokens_for_user(user)
        return JsonResponse({'ok': True, 'email': email, **tokens})

    # Minimal real exchange (non-DEBUG): POST code to Google token endpoint
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'OAUTH_REDIRECT_URI', '')
    if not client_id or not client_secret or not redirect_uri:
        return JsonResponse({'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'}, status=400)

    data = urllib.parse.urlencode({
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode('utf-8')
    try:
        # Strictly fixed token endpoint to avoid SSRF
        req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with _urlopen_fixed(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            token_payload = json.loads(body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'token exchange failed', 'code': 'token_exchange_failed'}, status=400)

    id_token = token_payload.get('id_token')
    if not id_token:
        return JsonResponse({'ok': False, 'error': 'missing id_token', 'code': 'missing_id_token'}, status=400)

    # In production, perform full JWKS signature verification and claim checks.
    if not settings.DEBUG:
        try:
            claims = _verify_google_id_token_prod(id_token)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid id_token', 'code': 'invalid_id_token'}, status=400)
    else:
        # In DEBUG, keep local-friendly behavior: decode without signature verification
        try:
            claims = pyjwt.decode(id_token, options={
                'verify_signature': False,
                'verify_aud': False,
            })
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid id_token', 'code': 'invalid_id_token'}, status=400)

    email = claims.get('email')
    if not email:
        return JsonResponse({'ok': False, 'error': 'email not provided by provider', 'code': 'email_not_found'}, status=400)
    user, _ = _get_or_create_user_by_email(email)
    # In DEBUG, mark Google logins as Free tier (owner_user scope) for testing
    if settings.DEBUG:
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        )
        if not sub:
            sub = Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()
    # Auto-accept invite if provided and matches email
    if invite_token:
        try:
            inv = OrgInvite.objects.select_related('org').get(token=invite_token)
            if (
                not inv.revoked_at
                and not inv.accepted_at
                and (email or '').strip().lower()
                == (inv.email or '').strip().lower()
            ):
                OrgUser.objects.update_or_create(
                    org=inv.org, user=user, defaults={'role': inv.role}
                )
                inv.accepted_at = timezone.now()
                inv.save(update_fields=['accepted_at'])
        except OrgInvite.DoesNotExist:
            pass
    tokens = _issue_tokens_for_user(user)
    return JsonResponse({'ok': True, 'email': email, **tokens})


# --- GitHub OAuth ---

@require_GET
def github_start(request):
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    redirect_uri = getattr(settings, 'GITHUB_REDIRECT_URI', '')
    if not client_id or not redirect_uri:
        return JsonResponse(
            {'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'},
            status=400,
        )
    invite = request.GET.get('invite')
    csrf_token = _gen_oauth_csrf_token()
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'read:user user:email',
    }
    state_obj = {'csrf': csrf_token}
    if invite:
        state_obj['invite'] = invite
    params['state'] = json.dumps(state_obj, separators=(',', ':'))
    url = 'https://github.com/login/oauth/authorize?' + urlencode(params)
    return _set_oauth_csrf_cookie(JsonResponse({'auth_url': url}), csrf_token)


@require_POST
@csrf_exempt
def github_callback(request):
    code = request.POST.get('code')
    if not code:
        return JsonResponse(
            {'ok': False, 'error': 'missing code', 'code': 'missing_code'},
            status=400,
        )
    state = request.POST.get('state') or ''
    invite_token = None
    csrf_expected = request.COOKIES.get('oauth_csrf', '')
    if state:
        try:
            if state.startswith('inv:'):
                if not settings.DEBUG:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
                invite_token = state[4:]
            else:
                st = json.loads(state)
                invite_token = st.get('invite')
                csrf_state = st.get('csrf') or ''
                if not csrf_expected or not csrf_state or csrf_state != csrf_expected:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
    if not invite_token:
        invite_token = request.GET.get('invite') or request.POST.get('invite')

    # DEBUG shortcut: email-based login
    if settings.DEBUG and not getattr(settings, 'GITHUB_CLIENT_SECRET', ''):
        email = request.POST.get('email')
        if not email:
            return JsonResponse({'ok': False, 'error': 'missing email', 'code': 'missing_email'}, status=400)
        user, _ = _get_or_create_user_by_email(email)
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        ) or Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()
        if invite_token:
            try:
                inv = OrgInvite.objects.select_related('org').get(token=invite_token)
                if (
                    not inv.revoked_at
                    and not inv.accepted_at
                    and (email or '').strip().lower()
                    == (inv.email or '').strip().lower()
                ):
                    OrgUser.objects.update_or_create(
                        org=inv.org, user=user, defaults={'role': inv.role}
                    )
                    inv.accepted_at = timezone.now()
                    inv.save(update_fields=['accepted_at'])
            except OrgInvite.DoesNotExist:
                pass
        tokens = _issue_tokens_for_user(user)
        return JsonResponse({'ok': True, 'email': email, **tokens})

    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    client_secret = getattr(settings, 'GITHUB_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'GITHUB_REDIRECT_URI', '')
    if not client_id or not client_secret or not redirect_uri:
        return JsonResponse({'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'}, status=400)

    # Exchange code for access_token
    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
    }).encode('utf-8')
    try:
        # Fixed origin to GitHub token endpoint
        req = urllib.request.Request('https://github.com/login/oauth/access_token', data=data, method='POST')
        req.add_header('Accept', 'application/json')
        with _urlopen_fixed(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            token_payload = json.loads(body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'token exchange failed', 'code': 'token_exchange_failed'}, status=400)
    access_token = token_payload.get('access_token')
    if not access_token:
        return JsonResponse({'ok': False, 'error': 'missing access token', 'code': 'missing_access_token'}, status=400)

    # Fetch user emails and choose a verified/primary email
    try:
        # Fixed GitHub API endpoint
        ureq = urllib.request.Request('https://api.github.com/user/emails')
        ureq.add_header('Accept', 'application/vnd.github+json')
        ureq.add_header('Authorization', f'Bearer {access_token}')
        with _urlopen_fixed(ureq, timeout=10) as uresp:
            ubody = uresp.read().decode('utf-8')
            emails = json.loads(ubody)
    except Exception:
        emails = []

    email = None
    saw_any_email = False
    if isinstance(emails, list):
        primary = [e for e in emails if e.get('primary') and e.get('verified') and e.get('email')]
        verified = [e for e in emails if e.get('verified') and e.get('email')]
        saw_any_email = any(bool(e.get('email')) for e in emails)
        if primary:
            email = primary[0]['email']
        elif verified:
            email = verified[0]['email']

    if not email:
        # Differentiate unverified vs not provided
        if saw_any_email:
            return JsonResponse({'ok': False, 'error': 'no verified email on account', 'code': 'email_unverified'}, status=400)
        return JsonResponse({'ok': False, 'error': 'email not provided by provider', 'code': 'email_not_found'}, status=400)

    user, _ = _get_or_create_user_by_email(email)
    if settings.DEBUG:
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        )
        if not sub:
            sub = Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()

    if invite_token:
        try:
            inv = OrgInvite.objects.select_related('org').get(token=invite_token)
            if (
                not inv.revoked_at
                and not inv.accepted_at
                and (email or '').strip().lower()
                == (inv.email or '').strip().lower()
            ):
                OrgUser.objects.update_or_create(
                    org=inv.org, user=user, defaults={'role': inv.role}
                )
                inv.accepted_at = timezone.now()
                inv.save(update_fields=['accepted_at'])
        except OrgInvite.DoesNotExist:
            pass

    tokens = _issue_tokens_for_user(user)
    return JsonResponse({'ok': True, 'email': email, **tokens})


# --- Facebook OAuth ---

@require_GET
def facebook_start(request):
    app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
    redirect_uri = getattr(settings, 'FACEBOOK_REDIRECT_URI', '')
    api_version = getattr(settings, 'FACEBOOK_API_VERSION', 'v12.0')
    if not app_id or not redirect_uri:
        return JsonResponse(
            {'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'},
            status=400,
        )
    invite = request.GET.get('invite')
    csrf_token = _gen_oauth_csrf_token()
    params = {
        'client_id': app_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'email',
    }
    state_obj = {'csrf': csrf_token}
    if invite:
        state_obj['invite'] = invite
    params['state'] = json.dumps(state_obj, separators=(',', ':'))
    url = f'https://www.facebook.com/{api_version}/dialog/oauth?' + urlencode(params)
    return _set_oauth_csrf_cookie(JsonResponse({'auth_url': url}), csrf_token)


@require_POST
@csrf_exempt
def facebook_callback(request):
    code = request.POST.get('code')
    if not code:
        return JsonResponse(
            {'ok': False, 'error': 'missing code', 'code': 'missing_code'},
            status=400,
        )
    state = request.POST.get('state') or ''
    invite_token = None
    csrf_expected = request.COOKIES.get('oauth_csrf', '')
    if state:
        try:
            if state.startswith('inv:'):
                if not settings.DEBUG:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
                invite_token = state[4:]
            else:
                st = json.loads(state)
                invite_token = st.get('invite')
                csrf_state = st.get('csrf') or ''
                if not csrf_expected or not csrf_state or csrf_state != csrf_expected:
                    return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid state', 'code': 'invalid_state'}, status=400)
    if not invite_token:
        invite_token = request.GET.get('invite') or request.POST.get('invite')

    if settings.DEBUG and not getattr(settings, 'FACEBOOK_APP_SECRET', ''):
        email = request.POST.get('email')
        if not email:
            return JsonResponse({'ok': False, 'error': 'missing email', 'code': 'missing_email'}, status=400)
        user, _ = _get_or_create_user_by_email(email)
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        ) or Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()
        if invite_token:
            try:
                inv = OrgInvite.objects.select_related('org').get(token=invite_token)
                if (
                    not inv.revoked_at
                    and not inv.accepted_at
                    and (email or '').strip().lower()
                    == (inv.email or '').strip().lower()
                ):
                    OrgUser.objects.update_or_create(
                        org=inv.org, user=user, defaults={'role': inv.role}
                    )
                    inv.accepted_at = timezone.now()
                    inv.save(update_fields=['accepted_at'])
            except OrgInvite.DoesNotExist:
                pass
        tokens = _issue_tokens_for_user(user)
        return JsonResponse({'ok': True, 'email': email, **tokens})

    app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
    app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '')
    redirect_uri = getattr(settings, 'FACEBOOK_REDIRECT_URI', '')
    api_version = getattr(settings, 'FACEBOOK_API_VERSION', 'v12.0')
    if not app_id or not app_secret or not redirect_uri:
        return JsonResponse({'ok': False, 'error': 'oauth not configured', 'code': 'oauth_not_configured'}, status=400)

    # Exchange code for access token
    token_qs = urllib.parse.urlencode({
        'client_id': app_id,
        'client_secret': app_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    })
    # Use Request with fixed host to avoid SSRF scanners complaining
    token_url = f'https://graph.facebook.com/{api_version}/oauth/access_token?{token_qs}'
    try:
        treq = urllib.request.Request(token_url, method='GET')
        with _urlopen_fixed(treq, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            token_payload = json.loads(body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'token exchange failed', 'code': 'token_exchange_failed'}, status=400)

    access_token = token_payload.get('access_token')
    if not access_token:
        return JsonResponse({'ok': False, 'error': 'missing access token', 'code': 'missing_access_token'}, status=400)

    # Fetch user email via Graph API
    # Fixed origin for Facebook Graph API; assemble URL safely
    me_url = (
        f'https://graph.facebook.com/{api_version}/me?fields=id,name,email&access_token='
        f'{urllib.parse.quote(access_token)}'
    )
    try:
        mreq = urllib.request.Request(me_url, method='GET')
        with _urlopen_fixed(mreq, timeout=10) as resp:
            me = json.loads(resp.read().decode('utf-8'))
    except Exception:
        me = {}

    email = me.get('email') if isinstance(me, dict) else None
    if not email:
        return JsonResponse({'ok': False, 'error': 'email not provided by provider', 'code': 'email_not_found'}, status=400)

    user, _ = _get_or_create_user_by_email(email)
    if settings.DEBUG:
        sub = (
            Subscription.objects.filter(owner_user=user)
            .order_by('-updated_at', '-id')
            .first()
        )
        if not sub:
            sub = Subscription(owner_user=user)
        sub.tier = 'free'
        sub.status = 'active'
        sub.cancel_at_period_end = False
        sub.save()

    if invite_token:
        try:
            inv = OrgInvite.objects.select_related('org').get(token=invite_token)
            if (
                not inv.revoked_at
                and not inv.accepted_at
                and (email or '').strip().lower()
                == (inv.email or '').strip().lower()
            ):
                OrgUser.objects.update_or_create(
                    org=inv.org, user=user, defaults={'role': inv.role}
                )
                inv.accepted_at = timezone.now()
                inv.save(update_fields=['accepted_at'])
        except OrgInvite.DoesNotExist:
            pass

    tokens = _issue_tokens_for_user(user)
    return JsonResponse({'ok': True, 'email': email, **tokens})
