# Granterstellar — AI Agent Guide (2025-08-30)

Purpose: Minimize tokens, maximize execution. This file targets agentic AI only.

## Protocol (always)
- Before edits/commands, post a compact change intent: goal, files, risks, validation (build/tests/lint). If the user asks to proceed, the request overrides approval.
- Prioritize Todo.md. Preempt only for: security issues, failing builds/tests/linters, or blocking inconsistencies. Note preemption reason.
- Validate after changes: run relevant tasks; report PASS/FAIL deltas only.

## Product & stack
- SaaS for guided grant writing. Exports to Markdown → DOCX/PDF. Freemium + paid.
- Monolith: React SPA (Vite) + Django (DRF). Postgres with RLS (JSONB content). Optional Celery/Redis. Coolify + Traefik deploy.
- Domains: test https://grants.intelfy.dk, prod https://forgranted.io. Umami host https://data.intelfy.dk (script.js).

## Core flows
- Authoring: SPA collects answers → API AI draft/revise → autosave PATCH into JSONB.
- Exports: POST /api/exports → canonical markdown → docx/pdf (deterministic; checksums).
- Billing: Stripe checkout/portal/webhooks; quotas by plan/seat; extras bundles (1/10/25). Usage at GET /api/usage (respects X-Org-ID).
- AI: provider abstraction (`ai/provider.py`). Default composite: GPT-5 plans/writes; Gemini formats/polishes. `file_refs` accepted; when present, outputs append deterministic `[context:sources]` with `- name: <ocr snippet>`. Optional async (`AI_ASYNC=1`): POST returns `{job_id}`, poll GET `/api/ai/jobs/{id}`.

## Access & RLS semantics
- Session GUCs via `accounts.middleware.RLSSessionMiddleware`: `app.current_user_id()`, `app.current_org_id()`, `app.current_role()`.
- Proposals READ: author; users in `shared_with`; org admins of `org_id`.
- Proposals WRITE: personal by author; org-scoped by org admin.
- OrgUser: READ self; INSERT/UPDATE/DELETE by org admin or when `(current_role='admin' and current_org_id=org_id)`.
- Organizations: INSERT (allowed; visibility via SELECT policy), DELETE by admin.
- Subscriptions: owner_user or org admin of owner_org.
- FORCE RLS enabled on orgs_organization, orgs_orguser, proposals_proposal, billing_subscription.
- Policies in `db_policies/migrations/0001_rls.py` (+ subsequent migrations 0002–0009). Postgres-only tests in `db_policies/tests/*` (skipped on SQLite).

## Security & hardening
- Strict CSP/security headers (env allow-lists). No source maps in prod; strip console/debugger. Images exclude docs/tests/maps.
- Landing server: known hosts only; static GET/HEAD rate limiting.
- Upload safety: MEDIA_ROOT containment; MIME/magic validation; served file signature checks; optional virus-scan hook.
- SPA `safeOpenExternal` enforces https + allow-list; test-mode opens unconditionally.
- Optional: API image build arg `STRIP_PY=1` compiles to .pyc and drops sources.

## Frontend
- Router base `/app` (`VITE_ROUTER_BASE`); asset base `/static/app/` (`VITE_BASE_URL`).
- Dev-only UI experiments via `VITE_UI_EXPERIMENTS`. Umami optional via `VITE_UMAMI_*`.
- Tests (Vitest/jsdom) rely on test-mode guards; avoid direct `location` changes in unit tests.

## Analytics & metrics
- AI metrics v2 logged per call: tokens, duration, model, user, org, proposal_id, section_id.
- GET `/api/ai/metrics/summary` (aggregates), GET `/api/ai/metrics/recent` (recent).

## Quotas
- Defaults: QUOTA_FREE_ACTIVE_CAP=1; QUOTA_PRO_MONTHLY_CAP=20; QUOTA_PRO_PER_SEAT=10; enterprise optional.
- Effective Pro cap = seats*per_seat + extras. Enforcement blocks proposal create with 402 + X-Quota-Reason (permission `billing.permissions.CanCreateProposal`).

## Async toggles
- Exports async: `EXPORTS_ASYNC=1`.
- AI async: `AI_ASYNC=1`.
- Celery requires `REDIS_URL` (broker/backend can be configured).

## Endpoints & quick refs
- Auth/JWT: POST `/api/token`, `/api/token/refresh`. OAuth: `/api/oauth/<provider>/*` (Google, GitHub, Facebook).
- Proposals: `api/proposals/models.py`, `api/proposals/views.py`.
- AI: `api/ai/provider.py`, `api/ai/views.py`, `api/ai/tasks.py`.
- Exports: `api/exports/utils.py`, `api/exports/views.py` (and `api/exports/tasks.py` if async).
- Billing: `api/billing/models.py`, `api/billing/quota.py`, `api/billing/views.py`, `api/billing/webhooks.py`.
- Files/OCR: `api/files/views.py` (txt/docx/pdf; optional image/PDF OCR via env toggles).
- Security middleware/CSP: `api/app/middleware.py`; CSP envs in `api/app/settings.py`.
- RLS GUC middleware: `api/accounts/middleware.py`. Policies SQL: `api/db_policies/migrations/*`.
- Useful ops: `scripts/media_backup.sh`; orphan scan: `api/files/management/commands/list_orphaned_media.py`.

## VS Code tasks (local)
- API: migrate; runserver (DEBUG); lint (ruff); tests (per-app); RLS tests on Postgres.
- Web: dev; lint.
- Celery worker (optional): requires Redis.

## Environment keys (high-impact)
- Core: SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL, REDIS_URL, PUBLIC_BASE_URL.
- Security: SECURE_* (HSTS, SSL redirect, referrer policy), SESSION_/CSRF_* (secure/samesite), CSP_SCRIPT_SRC, CSP_STYLE_SRC, CSP_CONNECT_SRC, CSP_ALLOW_INLINE_STYLES.
- OAuth: GOOGLE_*, GITHUB_*, FACEBOOK_*, OAUTH_REDIRECT_URI, GOOGLE_JWKS_URL, GOOGLE_ISSUER.
- Async: EXPORTS_ASYNC, AI_ASYNC, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_ALWAYS_EAGER.
- SPA: VITE_BASE_URL, VITE_API_BASE, VITE_ROUTER_BASE, VITE_UMAMI_WEBSITE_ID, VITE_UMAMI_SRC, VITE_UI_EXPERIMENTS.
- Email: INVITE_SENDER_DOMAIN, EMAIL_* (host, port, user, password, TLS), FRONTEND_INVITE_URL_BASE.
- Billing: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_PRO_MONTHLY, PRICE_PRO_YEARLY, PRICE_ENTERPRISE_MONTHLY, PRICE_BUNDLE_1/10/25.
- Uploads/OCR: FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE, TEXT_EXTRACTION_MAX_BYTES, ALLOWED_UPLOAD_EXTENSIONS, OCR_IMAGE, OCR_PDF, optional VIRUSSCAN_*.
- Quotas: QUOTA_FREE_ACTIVE_CAP, QUOTA_PRO_MONTHLY_CAP, QUOTA_PRO_PER_SEAT, QUOTA_ENTERPRISE_MONTHLY_CAP.
- AI provider: AI_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY.
- Orgs/Invites: ORG_INVITE_TTL_DAYS, ORG_INVITES_PER_HOUR, APP_HOSTS.

## CI & release invariants
- web/dist: no source maps; no console/debugger strings.
- Images: exclude docs/tests/maps; API supports `STRIP_PY=1`.
- Host header: reject untrusted; CSP allow-lists minimal and env-driven.

## Testing
- Django: run per app `python manage.py test -v 2 <app>` (avoid discovery collisions). RLS tests are Postgres-only.
- Exports determinism; billing seats/extras; failed-payment grace and cancel flows; AI metrics capture/summary.
- Web: Vitest/jsdom with test-mode guards.

## Docs pointers (for deeper detail)
- Install & envs: `docs/install_guide.md`
- Security hardening: `docs/security_hardening.md`
- RLS: `docs/rls_postgres.md`
- Ops: `docs/ops_runbook.md`

Consistency: If docs and code diverge, trust code; update this file and cross-referenced docs; reflect all changes in `Todo.md` if they have a corresponding task. Reflect all major changes in `Todo.md` with comments and annotations near corresponding tasks if there is no directly corresponding task.