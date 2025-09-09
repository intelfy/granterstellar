import json
import re
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_INVISIBLE_RE = re.compile(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]')


def _clean_value(v):
    if isinstance(v, str):
        s = v.replace('\r\n', '\n').replace('\r', '\n')
        s = _CTRL_RE.sub('', s)
        s = _INVISIBLE_RE.sub('', s)
        return s
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean_value(x) for k, x in v.items()}
    return v


class SanitizeJsonBodyMiddleware(MiddlewareMixin):
    """Best-effort JSON body sanitizer removing control/invisible characters from strings.

    Only applies to requests with Content-Type: application/json and a JSON body.
    """

    def process_request(self, request):
        if request.content_type and request.content_type.startswith('application/json'):
            try:
                # Reading body requires buffering and reassigning
                body = request.body
                if not body:
                    return None
                data = json.loads(body.decode('utf-8'))
                cleaned = _clean_value(data)
                if cleaned != data:
                    request._body = json.dumps(cleaned).encode('utf-8')
            except Exception:
                # If parsing fails, let normal handling occur
                return None
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add strict security headers in production.

    - Content-Security-Policy: lock down sources; allow same-origin assets and data: for images/fonts.
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: minimal defaults
    """

    def process_response(self, request, response):
        if not settings.DEBUG:
            extra_script = ' ' + ' '.join(settings.CSP_SCRIPT_SRC) if getattr(settings, 'CSP_SCRIPT_SRC', None) else ''
            extra_style = ' ' + ' '.join(settings.CSP_STYLE_SRC) if getattr(settings, 'CSP_STYLE_SRC', None) else ''
            extra_connect = ' ' + ' '.join(settings.CSP_CONNECT_SRC) if getattr(settings, 'CSP_CONNECT_SRC', None) else ''
            # Avoid allowing inline styles by default. If an emergency requires it, set
            # CSP_ALLOW_INLINE_STYLES=1 in the environment (not recommended).
            allow_inline = getattr(settings, 'CSP_ALLOW_INLINE_STYLES', False)
            style_src = "style-src 'self'" + (" 'unsafe-inline'" if allow_inline else '') + (extra_style or '')
            csp = (
                "default-src 'self'; "
                f"script-src 'self'{extra_script}; "
                f'{style_src}; '
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                # Allow only same-origin by default; extend via CSP_CONNECT_SRC allow-list
                f"connect-src 'self'{extra_connect}; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            # Do not override if app sets explicitly elsewhere
            response.setdefault('Content-Security-Policy', csp)
            response.setdefault('X-Content-Type-Options', 'nosniff')
            response.setdefault('X-Frame-Options', 'DENY')
            response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
            response.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
            # Extra isolation headers (mirrors landing server)
            response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
            response.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
            response.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        return response
