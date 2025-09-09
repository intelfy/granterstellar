import os
from urllib.parse import urlparse
from django.core.management.base import BaseCommand
from django.conf import settings

REQUIRED_ALWAYS = [
    'SECRET_KEY',
    'PUBLIC_BASE_URL',
]

# These must differ for rotation strategy
DISTINCT_SECRET_PAIRS = [
    ('SECRET_KEY', 'JWT_SIGNING_KEY'),
]

# Conditional groups we validate when any member set
GROUPS = {
    'redis': {
        'vars': ['REDIS_URL'],
        'require_if': [
            'EXPORTS_ASYNC',
            'AI_ASYNC',
            'CELERY_BROKER_URL',
            'CELERY_RESULT_BACKEND',
        ],
    },
    'stripe': {
        'vars': ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        'any_required': [
            'PRICE_PRO_MONTHLY',
            'PRICE_PRO_YEARLY',
            'PRICE_BUNDLE_1',
            'PRICE_BUNDLE_10',
            'PRICE_BUNDLE_25',
        ],
    },
    'openai': {
        'vars': ['OPENAI_API_KEY'],
        'when': [('AI_PROVIDER', lambda v: v and 'openai' in v)],
    },
    'gemini': {
        'vars': ['GEMINI_API_KEY'],
        'when': [('AI_PROVIDER', lambda v: v and 'gemini' in v)],
    },
}

SECURITY_INVARIANTS = [
    ('ALLOWED_HOSTS', lambda v: '*' not in v.split(','), 'ALLOWED_HOSTS must not contain * in production'),
    ('CORS_ALLOW_ALL', lambda v: v in {'', '0', 'False', 'false', None}, 'CORS_ALLOW_ALL must be 0/empty in production'),
]

URL_MUST_BE_HTTPS = ['PUBLIC_BASE_URL']


class Command(BaseCommand):
    help = 'Validate environment configuration for common production pitfalls. Exits non-zero on failure.'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true', help='Fail on warnings as well as errors.')
        parser.add_argument('--debug', action='store_true', help='Print extra context.')

    def handle(self, *args, **options):
        errors: list[str] = []
        warnings: list[str] = []
        strict = options.get('strict')
        debug = options.get('debug')
        env = os.environ

        def get(name):
            return env.get(name)

        # 1. Required always
        for var in REQUIRED_ALWAYS:
            if not get(var):
                errors.append(f'Missing required variable: {var}')

        # 2. Distinct secret pairs
        for a, b in DISTINCT_SECRET_PAIRS:
            av, bv = get(a), get(b)
            # Require both present in production and distinct
            if not av:
                errors.append(f'Missing required variable: {a}')
            if not bv:
                errors.append(f'Missing required variable: {b}')
            if av and bv and av == bv:
                errors.append(f'{b} should differ from {a} for rotation safety')

        # 3. Conditional groups
        if not settings.DEBUG:
            # Production-like hard checks
            for key, spec in GROUPS.items():
                when = spec.get('when') or []
                # Evaluate conditional 'when' clauses
                applicable = True
                for dep, predicate in when:
                    if not predicate(get(dep)):
                        applicable = False
                        break
                if not applicable:
                    continue
                required_vars = spec.get('vars', [])
                for rv in required_vars:
                    if not get(rv):
                        errors.append(f"Group '{key}' missing required var {rv}")
                # If any of require_if vars set, enforce presence of first group's vars
                for trigger in spec.get('require_if', []):
                    if get(trigger) and not all(get(rv) for rv in required_vars):
                        errors.append(f"{trigger} is set but required group '{key}' vars missing")
                # If any price set then require stripe secrets
                if key == 'stripe':
                    if any(get(v) for v in spec.get('any_required', [])):
                        if not all(get(v) for v in spec['vars']):
                            errors.append('Stripe price vars set but STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET missing')
        else:
            # In debug we downgrade missing conditional vars to warnings
            for key, spec in GROUPS.items():
                when = spec.get('when') or []
                applicable = True
                for dep, predicate in when:
                    if not predicate(get(dep)):
                        applicable = False
                        break
                if not applicable:
                    continue
                for rv in spec.get('vars', []):
                    if not get(rv):
                        warnings.append(f'[debug] Suggested var for {key} not set: {rv}')

        # 4. Security invariants (only if DEBUG=0)
        if not settings.DEBUG:
            for name, predicate, msg in SECURITY_INVARIANTS:
                val = get(name)
                if val is not None and not predicate(val):
                    errors.append(msg)

        # 5. HTTPS required URLs
        for name in URL_MUST_BE_HTTPS:
            val = get(name)
            if val:
                try:
                    p = urlparse(val)
                    if p.scheme != 'https':
                        warnings.append(f'{name} should be https (got: {val})')
                except Exception:
                    warnings.append(f'{name} is not a valid URL: {val}')

        # 6. Print summary
        for w in warnings:
            self.stdout.write(self.style.WARNING(f'WARN: {w}'))
        if errors:
            for e in errors:
                self.stderr.write(self.style.ERROR(f'ERROR: {e}'))
            self.stderr.write(self.style.ERROR(f'env_doctor failed with {len(errors)} error(s).'))
            raise SystemExit(1 if not strict else 2)
        self.stdout.write(self.style.SUCCESS('env_doctor passed with no fatal errors.'))
        if debug:
            self.stdout.write('DEBUG VAR SNAPSHOT:')
            for k in sorted(env):
                if k.isupper() and any(k.startswith(prefix) for prefix in ('STRIPE', 'OPENAI', 'GEMINI', 'SECRET', 'JWT')):
                    continue  # avoid leaking secrets
                self.stdout.write(f'  {k}={env[k]}')
