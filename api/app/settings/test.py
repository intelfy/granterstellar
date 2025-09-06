from . import base

for k, v in base.__dict__.items():
    if k.isupper():
        globals()[k] = v

# Test overrides (executed when DJANGO_ENV=test or manage.py test sets 'test' in argv)
DEBUG = True
AI_TEST_OPEN = True
CELERY_TASK_ALWAYS_EAGER = True  # ensure tasks run inline for assertions
