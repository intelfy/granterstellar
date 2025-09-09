[[AI_CONFIG]]
FILE_TYPE: 'OPS_RUNBOOK'
INTENDED_READER: 'BOTH_HUMAN_AND_AI_AGENT'
PURPOSE: ['Provide quick reference for on-call ops', 'Guide troubleshooting of common issues', 'Document health checks and recovery steps', 'Ensure reliable deployment and maintenance']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

# Ops runbook (on-call quick reference)

This is a minimal checklist for verifying health, diagnosing common issues, and applying quick fixes.

## Health and smoke checks

- API liveness: GET /api/health (200 OK if process responding)
- API readiness: GET /api/ready (200 OK only if DB + cache reachable; standardized error JSON otherwise)
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
    - 429 Too Many Requests on second rapid call (expected in DEBUG with deterministic single-write guard)
    - Unexpected 429s under light load
  - Layers (executed by `ai_protected` decorator):
    - Plan gating (Pro/Enterprise required; bypass in DEBUG / AI_TEST_OPEN)
    - Deterministic single-write debug guard (opt-in via env)
    - Cache fast path (approximate per-minute bucket) for early rejection
    - Authoritative DB count (AIMetric window)
  - Key env vars:
    - AI_RATE_PER_MIN_FREE, AI_RATE_PER_MIN_PRO, AI_RATE_PER_MIN_ENTERPRISE
    - AI_ENFORCE_RATE_LIMIT_DEBUG (0/1)
    - AI_TEST_OPEN (optional bypass)
  - Checks:
    - Cache functioning (fast path + single-write guard rely on Django cache)
    - AIMetric rows increasing post-call (DB layer)
  - Fix:
    - Increase env RPM for legitimate higher load
    - Clear stuck cache key `ai_dbg_single_write:<user_id>` (or wait TTL)
    - Disable deterministic guard by unsetting AI_ENFORCE_RATE_LIMIT_DEBUG if interfering with manual testing
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

## Environment keys quick reference

Use the authoritative matrix in `docs/ops_coolify_deployment_guide.md` for full details (purpose, type, required flags). This section highlights only frequently triaged categories:

- Core: SECRET_KEY, ALLOWED_HOSTS, PUBLIC_BASE_URL, DEBUG
- Async toggles: EXPORTS_ASYNC, AI_ASYNC (require Redis/Celery)
- Billing: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_*, FAILED_PAYMENT_GRACE_DAYS
- Uploads & scanning: FILE_UPLOAD_MAX_BYTES, TEXT_EXTRACTION_MAX_BYTES, ALLOWED_UPLOAD_EXTENSIONS, VIRUSSCAN_*
- AI limits: AI_RATE_PER_MIN_*, AI_ENFORCE_RATE_LIMIT_DEBUG, AI_TEST_OPEN, AI_DETERMINISTIC_SAMPLING
- Security headers/CSP: CSP_* vars, SESSION/CSRF secure & samesite flags
- Quotas: QUOTA_* (active/monthly caps)

## Monitoring (lightweight ideas)

- Uptime: point an external monitor at `/healthz` and `/api/usage` (GET), expect 200 JSON.
- Logs: capture container stdout/stderr; search for `ERROR`/`CRITICAL` around Stripe webhooks and Celery workers.
- Metrics: optional logs-to-dashboard for request counts, 4xx/5xx rate, and job queue depth (Celery events).

## Docs

- Install & envs: `docs/ops_coolify_deployment_guide.md`
- Security hardening: `docs/security_hardening.md`
- RLS: `docs/rls_postgres.md`
- AI rate limiting: `docs/ai_rate_limiting.md`
- Exports architecture & determinism: `docs/exports.md`
- Docs index: `docs/README.md`
