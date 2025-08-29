import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

# Secure-by-default: DEBUG off unless explicitly enabled
DEBUG = os.getenv('DEBUG', '0') == '1'

# Require explicit hosts; defaults safe for local dev
ALLOWED_HOSTS = [h for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h]
# Allow Django test client host during local/dev
if os.getenv('DEBUG', '0') == '1':
    for h in ('testserver',):
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'accounts',
    'billing',
    'orgs',
    'proposals',
    'db_policies',
    'ai',
    'exports',
    'files',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'app.middleware.SanitizeJsonBodyMiddleware',
    'app.middleware.SecurityHeadersMiddleware',
    # Session should come before Common/CSRF so sessions work correctly
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # App-specific middlewares
    'accounts.middleware.RLSSessionMiddleware',
    'billing.middleware.QuotaEnforcementMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

DATABASES = {
    'default': dj_database_url.parse(os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'), conn_max_age=600)
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# Ensure static files are immutable and fingerprinted in production.
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

# Media (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# CORS: deny-all by default; allow-list via env
CORS_ALLOW_ALL_ORIGINS = True if os.getenv('CORS_ALLOW_ALL', '0') == '1' else False
CORS_ALLOWED_ORIGINS = [o for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o] if not CORS_ALLOW_ALL_ORIGINS else []
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', '0') == '1'

# CSRF trusted origins (comma-separated, e.g., https://app.example.com,https://api.example.com)
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security headers and cookies (assumes TLS termination by Traefik)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '1' if not DEBUG else '0') == '1'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '1' if not DEBUG else '0') == '1'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', '1' if not DEBUG else '0') == '1'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', '1' if not DEBUG else '0') == '1'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', '1' if not DEBUG else '0') == '1'
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')

# Optional CSP host allow-list for scripts/styles/connect (comma-separated)
CSP_SCRIPT_SRC = [o for o in os.getenv('CSP_SCRIPT_SRC', '').split(',') if o]
CSP_STYLE_SRC = [o for o in os.getenv('CSP_STYLE_SRC', '').split(',') if o]
CSP_CONNECT_SRC = [o for o in os.getenv('CSP_CONNECT_SRC', '').split(',') if o]

# Optional list of hostnames that should default to the SPA (e.g., app.<domain>)
APP_HOSTS = [h.strip() for h in os.getenv('APP_HOSTS', '').split(',') if h.strip()]

# Cookies SameSite and HttpOnly
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')

# DRF defaults: lock down in production
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny' if DEBUG else 'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
    'rest_framework_simplejwt.authentication.JWTAuthentication',
    'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': os.getenv('DRF_THROTTLE_USER', '100/min'),
        'anon': os.getenv('DRF_THROTTLE_ANON', '20/min'),
    },
    'DEFAULT_RENDERER_CLASSES': (
        ['rest_framework.renderers.JSONRenderer']
        if not DEBUG
        else [
            'rest_framework.renderers.JSONRenderer',
            'rest_framework.renderers.BrowsableAPIRenderer',
        ]
    ),
}

# Production safety checks
if not DEBUG:
    if SECRET_KEY == 'dev-secret-key':
        raise RuntimeError('SECURITY: SECRET_KEY must be set in production')
    if '*' in ALLOWED_HOSTS:
        raise RuntimeError('SECURITY: ALLOWED_HOSTS cannot include * in production')
    if CORS_ALLOW_ALL_ORIGINS:
        raise RuntimeError('SECURITY: CORS_ALLOW_ALL must be 0 in production')

# Quota defaults (can be overridden via env)
QUOTA_FREE_ACTIVE_CAP = int(os.getenv('QUOTA_FREE_ACTIVE_CAP', '1'))
QUOTA_PRO_MONTHLY_CAP = int(os.getenv('QUOTA_PRO_MONTHLY_CAP', '20'))
QUOTA_PRO_PER_SEAT = int(os.getenv('QUOTA_PRO_PER_SEAT', '10'))
QUOTA_ENTERPRISE_MONTHLY_CAP = os.getenv('QUOTA_ENTERPRISE_MONTHLY_CAP')
if QUOTA_ENTERPRISE_MONTHLY_CAP is not None and QUOTA_ENTERPRISE_MONTHLY_CAP != '':
    QUOTA_ENTERPRISE_MONTHLY_CAP = int(QUOTA_ENTERPRISE_MONTHLY_CAP)
else:
    QUOTA_ENTERPRISE_MONTHLY_CAP = None

# File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', str(10 * 1024 * 1024)))  # 10 MB default
ALLOWED_UPLOAD_EXTENSIONS = [
    ext.strip().lower() for ext in os.getenv(
        'ALLOWED_UPLOAD_EXTENSIONS', 'pdf,png,jpg,jpeg,docx,txt'
    ).split(',') if ext
]

# SimpleJWT defaults
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '30'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),
    'SIGNING_KEY': os.getenv('JWT_SIGNING_KEY', SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Celery (optional; configure REDIS_URL for broker/back-end)
CELERY_BROKER_URL = os.getenv('REDIS_URL', '')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', '')
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', '0') == '1'

# Feature flags
# When true and Celery broker is configured, export jobs will be enqueued instead of executed synchronously.
EXPORTS_ASYNC = os.getenv('EXPORTS_ASYNC', '0') == '1'
# When true and Celery broker is configured, AI endpoints will enqueue background jobs and return job_id for polling.
AI_ASYNC = os.getenv('AI_ASYNC', '0') == '1'

# Email/Invites
INVITE_SENDER_DOMAIN = os.getenv('INVITE_SENDER_DOMAIN', '').strip()
# Default from email prioritizes invites@<domain> when configured; else falls back to Mailgun domain or a generic no-reply.
DEFAULT_FROM_EMAIL = (
    (f"invites@{INVITE_SENDER_DOMAIN}" if INVITE_SENDER_DOMAIN else None)
    or (f"no-reply@{os.getenv('MAILGUN_DOMAIN', '').strip()}" if os.getenv('MAILGUN_DOMAIN', '').strip() else None)
    or 'no-reply@localhost'
)

# Stripe price configuration (optional; API can accept explicit price_id)
PRICE_PRO_MONTHLY = os.getenv('PRICE_PRO_MONTHLY', '').strip()
PRICE_PRO_YEARLY = os.getenv('PRICE_PRO_YEARLY', '').strip()
# Overage bundles (extras) — optional price ids for 1/10/25 proposal packs
PRICE_BUNDLE_1 = os.getenv('PRICE_BUNDLE_1', '').strip()
PRICE_BUNDLE_10 = os.getenv('PRICE_BUNDLE_10', '').strip()
PRICE_BUNDLE_25 = os.getenv('PRICE_BUNDLE_25', '').strip()