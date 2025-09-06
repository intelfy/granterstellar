[[AI_CONFIG]]
FILE_TYPE: 'OPS_RUNBOOK'
INTENDED_READER: 'BOTH_HUMAN_AND_AI_AGENT'
PURPOSE: ['Provide quick reference for on-call ops', 'Guide troubleshooting of common issues', 'Document health checks and recovery steps', 'Ensure reliable deployment and maintenance']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

# Ops runbook (on-call quick reference)

This is a minimal checklist for verifying health, diagnosing common issues, and applying quick fixes.

## Health and smoke checks

- API liveness: GET /healthz (200 ok)
- Usage payload: GET /api/usage (with and without X-Org-ID)
- SPA: visit /app (router loads; console clean in prod)
- Stripe webhook (DEBUG): POST /api/stripe/webhook with a test event

VS Code tasks

- API server: "API: runserver (DEBUG)"
- API tests (core): "API: test (accounts+billing+exports)"
- Web dev: "Web: dev"
- Celery worker: "API: celery worker" (requires Redis)

## Subsystems and quick triage

- Stripe webhooks
  - Symptom: subscription state not reflecting changes
  - Checks: logs around /api/stripe/webhook; verify STRIPE_WEBHOOK_SECRET in prod; replay event from Stripe dashboard
  - Fix: In DEBUG, unsigned events are accepted; in prod, set correct signing secret and replay. Locally, use Stripe CLI to forward events to `/api/stripe/webhook` and set the printed signing secret in the API env for parity.

- Quotas/paywall
  - Symptom: free users blocked or over-cap, Pro caps not applied
  - Checks: GET /api/usage; headers (X-Org-ID); env QUOTA_*; FAILED_PAYMENT_GRACE_DAYS
  - Fix: ensure subscription seats/extras present; verify Recent Stripe invoice webhook processed

- AI endpoints
  - Symptom: 402 ai_requires_pro in prod; async jobs not completing
  - Checks: DEBUG=0?; org scope header set?; Celery worker healthy when AI_ASYNC=1; Redis reachable
  - Fix: set DEBUG=1 locally (dev), or ensure active subscription; for async, start worker and confirm broker/backend env

- AI rate limiting & gating
  - Symptoms:
    - 429 Too Many Requests on second rapid call (expected in DEBUG with single-write guard)
    - Unexpected 429s under light load
  - Layers:
    - Plan gating (Pro/Enterprise required for some endpoints)
    - Per-minute tier limits (FREE / PRO / ENTERPRISE) via env-configured RPM
    - Deterministic single-write debug limiter (enforced only when AI_ENFORCE_RATE_LIMIT_DEBUG=1) for test stability
  - Key env vars:
    - AI_RATE_PER_MIN_FREE, AI_RATE_PER_MIN_PRO, AI_RATE_PER_MIN_ENTERPRISE
    - AI_ENFORCE_RATE_LIMIT_DEBUG (0/1)
    - AI_TEST_OPEN (if set, may relax gating for tests)
  - Checks:
    - Response headers: X-AI-Rate-Remaining, X-AI-Rate-Limit (if exposed)
    - Cache backend availability (single-write guard uses Django cache)
  - Fix:
    - Raise specific RPM env var for tier if legitimate traffic growth
    - Disable debug enforcement locally by unsetting AI_ENFORCE_RATE_LIMIT_DEBUG
    - Purge stale cache key `ai_dbg_single_write:<user_id>` if stuck (rare)
  - Reference: `docs/ai_rate_limiting.md`

- Exports
  - Symptom: export not generating or missing URL
  - Checks: EXPORTS_ASYNC setting; Celery worker status; media volume mounted
  - Fix: for async, ensure worker and Redis; otherwise synchronous path will return URL directly

- Uploads/OCR
  - Symptom: 400 mismatched_signature or infected; 413 file_too_large
  - Checks: ALLOWED_UPLOAD_EXTENSIONS, FILE_UPLOAD_MAX_BYTES, TEXT_EXTRACTION_MAX_BYTES, VIRUSSCAN_CMD
  - Fix: adjust env for caps; correct file type; review virus-scan command and timeout

## Backups and restore (high level)

- Database: use daily `pg_dump` artifacts (see `scripts/pg_dump_daily.sh` and compose/jobs). Test restore to a staging DB.
- Media: use `scripts/media_backup.sh` for snapshots to /backups. Restore by extracting into MEDIA_ROOT and verifying perms.

## Postgres RLS

- Policies live in `db_policies/migrations/0001_rls.py` (+ fixes in 0002)
- Tests are Postgres-only: run the task "API: test (RLS on Postgres)" with DATABASE_URL set
- Least-privileged DB role guidance: `docs/rls_postgres.md`
- Matrix coverage: see `db_policies/tests/test_rls_matrix.py` for consolidated CRUD + visibility scenarios. It deliberately emphasizes negative membership insertion (non-admin insert must fail) to guard least-privilege guarantees while keeping setup stable.

## Security headers and CSP

- Env allow-lists: CSP_SCRIPT_SRC, CSP_STYLE_SRC, CSP_CONNECT_SRC (comma-separated; 'self' auto-added)
- Avoid inline styles; CSP_ALLOW_INLINE_STYLES=1 is a temporary escape hatch only

## Useful environment keys

- Core: SECRET_KEY, DEBUG, ALLOWED_HOSTS, PUBLIC_BASE_URL
- Async: EXPORTS_ASYNC, AI_ASYNC, REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND
- OAuth: GOOGLE_*, GITHUB_*, FACEBOOK_* (see install guide)
- Billing: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_*; FAILED_PAYMENT_GRACE_DAYS
- Uploads: FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE, TEXT_EXTRACTION_MAX_BYTES, ALLOWED_UPLOAD_EXTENSIONS, VIRUSSCAN_*
- AI limits: AI_RATE_PER_MIN_FREE, AI_RATE_PER_MIN_PRO, AI_RATE_PER_MIN_ENTERPRISE, AI_ENFORCE_RATE_LIMIT_DEBUG, AI_TEST_OPEN

## Monitoring (lightweight ideas)

- Uptime: point an external monitor at `/healthz` and `/api/usage` (GET), expect 200 JSON.
- Logs: capture container stdout/stderr; search for `ERROR`/`CRITICAL` around Stripe webhooks and Celery workers.
- Metrics: optional logs-to-dashboard for request counts, 4xx/5xx rate, and job queue depth (Celery events).

## Docs

- Install & envs: `docs/ops_coolify_deployment_guide.md` (formerly install_guide)
- Security hardening: `docs/security_hardening.md`
- RLS: `docs/rls_postgres.md`
- AI rate limiting: `docs/ai_rate_limiting.md`
- Deterministic exports: `docs/deterministic_exports.md`
- Docs index: `docs/README.md`
