import os
import sys
from datetime import timedelta
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
DEBUG = os.getenv('DEBUG', '0') == '1'

ALLOWED_HOSTS = [h for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h]
if DEBUG:
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
    'app',
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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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

TESTING = 'test' in sys.argv
if TESTING:
    DEBUG = True
    AI_TEST_OPEN = True
    if 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')
else:
    AI_TEST_OPEN = False

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CORS_ALLOW_ALL_ORIGINS = True if os.getenv('CORS_ALLOW_ALL', '0') == '1' else False
CORS_ALLOWED_ORIGINS = [o for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o] if not CORS_ALLOW_ALL_ORIGINS else []
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', '0') == '1'
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '1' if not DEBUG else '0') == '1'
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '1' if not DEBUG else '0') == '1'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', '1' if not DEBUG else '0') == '1'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', '1' if not DEBUG else '0') == '1'
SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', '1' if not DEBUG else '0') == '1'
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')

CSP_SCRIPT_SRC = [o for o in os.getenv('CSP_SCRIPT_SRC', '').split(',') if o]
CSP_STYLE_SRC = [o for o in os.getenv('CSP_STYLE_SRC', '').split(',') if o]
CSP_CONNECT_SRC = [o for o in os.getenv('CSP_CONNECT_SRC', '').split(',') if o]
CSP_ALLOW_INLINE_STYLES = os.getenv('CSP_ALLOW_INLINE_STYLES', '0') == '1'

APP_HOSTS = [h.strip() for h in os.getenv('APP_HOSTS', '').split(',') if h.strip()]

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')

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
        'login': os.getenv('DRF_THROTTLE_LOGIN', '10/min'),
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

if not DEBUG:
    if SECRET_KEY == 'dev-secret-key':
        raise RuntimeError('SECURITY: SECRET_KEY must be set in production')
    if '*' in ALLOWED_HOSTS:
        raise RuntimeError('SECURITY: ALLOWED_HOSTS cannot include * in production')
    if CORS_ALLOW_ALL_ORIGINS:
        raise RuntimeError('SECURITY: CORS_ALLOW_ALL must be 0 in production')
    if not os.getenv('JWT_SIGNING_KEY'):
        raise RuntimeError('SECURITY: JWT_SIGNING_KEY must be set and distinct from SECRET_KEY in production')
    if os.getenv('JWT_SIGNING_KEY') == SECRET_KEY:
        raise RuntimeError('SECURITY: JWT_SIGNING_KEY must be different from SECRET_KEY for key rotation strategy')

QUOTA_FREE_ACTIVE_CAP = int(os.getenv('QUOTA_FREE_ACTIVE_CAP', '1'))
QUOTA_PRO_MONTHLY_CAP = int(os.getenv('QUOTA_PRO_MONTHLY_CAP', '20'))
QUOTA_PRO_PER_SEAT = int(os.getenv('QUOTA_PRO_PER_SEAT', '10'))
QUOTA_ENTERPRISE_MONTHLY_CAP = os.getenv('QUOTA_ENTERPRISE_MONTHLY_CAP')
if QUOTA_ENTERPRISE_MONTHLY_CAP is not None and QUOTA_ENTERPRISE_MONTHLY_CAP != '':
    QUOTA_ENTERPRISE_MONTHLY_CAP = int(QUOTA_ENTERPRISE_MONTHLY_CAP)
else:
    QUOTA_ENTERPRISE_MONTHLY_CAP = None

FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', str(10 * 1024 * 1024)))
FILE_UPLOAD_MAX_BYTES = int(os.getenv('FILE_UPLOAD_MAX_BYTES', str(FILE_UPLOAD_MAX_MEMORY_SIZE)))
TEXT_EXTRACTION_MAX_BYTES = int(os.getenv('TEXT_EXTRACTION_MAX_BYTES', str(8 * 1024 * 1024)))
VIRUSSCAN_CMD = os.getenv('VIRUSSCAN_CMD', '').strip()
VIRUSSCAN_TIMEOUT_SECONDS = int(os.getenv('VIRUSSCAN_TIMEOUT_SECONDS', '10'))
ALLOWED_UPLOAD_EXTENSIONS = [
    ext.strip().lower() for ext in os.getenv('ALLOWED_UPLOAD_EXTENSIONS', 'pdf,png,jpg,jpeg,docx,txt').split(',') if ext
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '30'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),
    'SIGNING_KEY': os.getenv('JWT_SIGNING_KEY', SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CELERY_BROKER_URL = os.getenv('REDIS_URL', '')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', '')
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', '0') == '1'

EXPORTS_ASYNC = os.getenv('EXPORTS_ASYNC', '0') == '1'
AI_ASYNC = os.getenv('AI_ASYNC', '0') == '1'

# AI Security Settings
AI_PROMPT_SHIELD_ENABLED = os.getenv('AI_PROMPT_SHIELD_ENABLED', '1') == '1'
AI_SECTION_REVISION_CAP = int(os.getenv('AI_SECTION_REVISION_CAP', '5'))

INVITE_SENDER_DOMAIN = os.getenv('INVITE_SENDER_DOMAIN', '').strip()
DEFAULT_FROM_EMAIL = (
    (f'invites@{INVITE_SENDER_DOMAIN}' if INVITE_SENDER_DOMAIN else None)
    or (f"no-reply@{os.getenv('MAILGUN_DOMAIN', '').strip()}" if os.getenv('MAILGUN_DOMAIN', '').strip() else None)
    or 'no-reply@localhost'
)

PRICE_PRO_MONTHLY = os.getenv('PRICE_PRO_MONTHLY', '').strip()
PRICE_PRO_YEARLY = os.getenv('PRICE_PRO_YEARLY', '').strip()
PRICE_BUNDLE_1 = os.getenv('PRICE_BUNDLE_1', '').strip()
PRICE_BUNDLE_10 = os.getenv('PRICE_BUNDLE_10', '').strip()
PRICE_BUNDLE_25 = os.getenv('PRICE_BUNDLE_25', '').strip()

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').strip()
