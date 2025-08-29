# Granterstellar API — Developer Quickstart and Smoke Tests

This README helps you spin up the Django API locally, seed a demo user, and run quick smoke tests without starting a server.

## Prerequisites
- Python 3.11+ (tested with 3.13)
- macOS/Linux shell (zsh/bash)

## Setup
```sh
# From repo root
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Local dev
export DEBUG=1

# Database (SQLite by default via dj-database-url)
python manage.py migrate
```

Optional: use Postgres by setting `DATABASE_URL` before `migrate`, e.g.
```sh
export DATABASE_URL=postgresql://user:pass@localhost:5432/granterstellar
```

## Seed a demo user + proposal (optional)
```sh
python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings')
os.environ['DEBUG'] = '1'
import django
django.setup()
from django.contrib.auth import get_user_model
from proposals.models import Proposal
User=get_user_model()
demo, _ = User.objects.get_or_create(username='demo', defaults={'email':'demo@example.com'})
demo.set_password('demo12345'); demo.save()
Proposal.objects.get_or_create(author=demo, content={
  "meta":{"title":"Test"},
  "sections":{"summary":{"title":"Executive Summary","content":"Lorem ipsum"}}
})
print('Seeded demo user and one proposal (if not present).')
PY
```

## Quick smoke tests (no server required)
Run a short script using Django's test client to hit key endpoints.
```sh
python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','app.settings')
os.environ['DEBUG'] = '1'
import django
django.setup()
from django.test import Client
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

c = Client()
print('health:', c.get('/healthz').status_code)

api = APIClient()
# JWT token (requires seeded demo)
tr = api.post('/api/token', {'username':'demo','password':'demo12345'}, format='json')
print('token:', tr.status_code, list(getattr(tr,'data',{}).keys()))

# AI endpoints
print('ai/plan:', api.post('/api/ai/plan', {'grant_url':'https://example.com/grant'}, format='json').status_code)

# Create an export (pdf) for first proposal if any
pr = api.get('/api/proposals/')
if pr.status_code == 200 and isinstance(pr.json(), list) and pr.json():
    pid = pr.json()[0]['id']
    er = api.post('/api/exports', {'proposal_id': pid, 'format': 'pdf'}, format='json')
    print('export pdf:', er.status_code, er.json())

# Upload a txt file
suf = SimpleUploadedFile('sample.txt', b'hello world', content_type='text/plain')
ur = api.post('/api/files', {'file': suf}, format='multipart')
print('upload txt:', ur.status_code, ur.json().get('url'))
PY
```

## Run the dev server (optional)
```sh
python manage.py runserver 127.0.0.1:8000
# Then: curl -sS http://127.0.0.1:8000/healthz
```

Note: In DEBUG, `testserver` is allowed automatically for Django's test client.

## Tests
Run Django tests per app to avoid discovery collisions:
```sh
# From api/
python manage.py test -v 2 accounts.tests.test_health \
  proposals.tests.test_api \
  billing.tests.test_quota \
  billing.tests.test_usage \
  billing.tests.test_webhooks
```

## Key endpoints (implemented)
- GET /healthz
- Auth: POST /api/token, POST /api/token/refresh (JWT)
- OAuth (scaffold): GET /api/oauth/google/start, GET /api/oauth/google/callback
- GET /api/usage (X-Org-ID supported)
- Billing: GET /api/billing/portal (Stripe portal; placeholder URL in DEBUG)
          POST /api/billing/checkout (creates checkout session; DEBUG placeholder URL)
          POST /api/billing/cancel (marks cancel at period end for current subscription)
          POST /api/billing/resume (clears cancel at period end)
          POST /api/stripe/webhook (Stripe events; requires signature in prod)

Maintenance
- Period enforcement safety-net (runs if webhooks are missed):
  - python manage.py enforce_subscription_periods
# AI endpoints:
  - POST /api/ai/plan
  - POST /api/ai/write
  - POST /api/ai/revise
  - POST /api/ai/format (final formatting pass after all sections are approved)
  - GET /api/ai/jobs/{id} → {status,result,error}

Async (optional):
- Set AI_ASYNC=1 and configure REDIS_URL for Celery broker/back-end.
- When enabled, the above POST endpoints return {job_id,status} and you can poll GET /api/ai/jobs/{id} for completion.
- Proposals: /api/proposals (scoped; create enforces quota)
- Exports: POST /api/exports (format: md|pdf|docx), GET /api/exports/{id}
- Files: POST /api/files (pdf/png/jpg/jpeg/docx/txt); txt/docx text extraction stub
  - Text extraction: txt/docx parsed; PDFs extracted via pdfminer; optional OCR for images (OCR_IMAGE=1) and PDFs (OCR_PDF=1 with `ocrmypdf` binary installed)

## Troubleshooting
- DisallowedHost testserver: allowed automatically in DEBUG in settings.
- 402 on POST /api/proposals: quota exceeded (free tier). Check /api/usage and X-Quota-Reason header.
- Export file not found: ensure DEBUG=1 (serves media) or proper MEDIA settings in production.
- Stripe webhook: in DEBUG without STRIPE_WEBHOOK_SECRET, unsigned events are accepted for local testing; in production, signature is required.

## Settings of note
- FAILED_PAYMENT_GRACE_DAYS: when > 0, a subscription in past_due remains treated as active within the grace window for quota checks.
- FILE_UPLOAD_MAX_BYTES: hard cap enforced by the upload API (413 on overflow). If unset, falls back to FILE_UPLOAD_MAX_MEMORY_SIZE.
- TEXT_EXTRACTION_MAX_BYTES: upper bound for txt/docx/pdf parsing; protects CPU/memory.
