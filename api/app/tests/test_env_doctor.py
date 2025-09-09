import os
from django.core.management import call_command
from django.test import SimpleTestCase


def _run_env_doctor(env: dict, strict: bool = False) -> int:
    backup = os.environ.copy()
    try:
        os.environ.update(env)
        args = []
        if strict:
            args.append('--strict')
        try:
            call_command('env_doctor', *args)
            return 0
        except SystemExit as e:  # command raises SystemExit for non-zero
            return int(e.code or 0)
    finally:
        os.environ.clear()
        os.environ.update(backup)


class EnvDoctorTests(SimpleTestCase):
    def test_price_requires_stripe_secrets_prod(self):
        """Production-like (DEBUG=0) with price set but missing stripe secrets => exit 1."""
        code = _run_env_doctor({
            'DEBUG': '0',  # production path => hard checks
            'SECRET_KEY': 'test',
            'PUBLIC_BASE_URL': 'https://example.com',
            'PRICE_PRO_MONTHLY': 'price_123',  # triggers stripe group requirement
            # Intentionally omit STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET
            'REDIS_URL': 'redis://localhost:6379/0',  # avoid unrelated redis error
        })
        self.assertEqual(code, 1)

    def test_strict_mode_warning_http_url_not_fatal(self):
        """HTTP base URL only produces warning; strict does not escalate warnings => exit 0."""
        code = _run_env_doctor({
            'DEBUG': '1',  # debug => conditional groups are warnings not errors
            'SECRET_KEY': 'test',
            'PUBLIC_BASE_URL': 'http://localhost:8000',  # causes https warning
            'REDIS_URL': 'redis://localhost:6379/0',
            'STRIPE_SECRET_KEY': 'sk_test_dummy',
            'STRIPE_WEBHOOK_SECRET': 'whsec_dummy',
        }, strict=True)
        self.assertEqual(code, 0)