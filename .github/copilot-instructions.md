# Granterstellar — AI Agent Guide (2025-08-29)

Purpose: Give an agent the minimum to be productive fast. Favor concise, current instructions over exhaustive detail.

## product and stack
- SaaS for guided grant writing. Export to Markdown → DOCX/PDF. Freemium + paid tiers. 
- Monolith: React SPA (Vite) + Django API (DRF). Postgres (JSONB) with RLS. Optional Celery/Redis. Deployed via Coolify behind Traefik.
- Proposal content lives as JSON in `proposals_proposal.content`.
 - Security hardening: strict CSP/security headers with env allow-lists; web build ships without source maps and with console/debugger stripped; images exclude docs/tests/maps.
   - Landing server does not trust Host header; known hosts only.
   - Static GET/HEAD rate limiting on landing endpoints to reduce abuse.
   - Upload safety: MEDIA_ROOT containment and MIME/magic validation; signature checks on served files.
   - SPA safe external navigation helper enforces https + allow-list; test-mode opens unconditionally for unit tests.
 - Optional backend obfuscation: API image supports `STRIP_PY=1` to compile to optimized .pyc and drop .py sources.
 - Domains (current plan): Test at https://grants.intelfy.dk; Production at https://forgranted.io. Umami analytics host: https://data.intelfy.dk (script.js).

## core flows
- Authoring: SPA collects answers → API AI endpoints draft sections → user approves/revises → JSONB updates (PATCH autosave).
- Exports: POST /api/exports → markdown canonical → docx/pdf; deterministic output/checksums.
- Billing: Stripe checkout/portal/webhooks; quotas per plan/seat; extras bundles (1/10/25). Usage lives at GET /api/usage (respects X-Org-ID).
 - AI metrics: logged per call with tokens/duration/model/user/org; includes proposal_id and section_id for pricing analytics. Summary at GET `/api/ai/metrics/summary`, recent at `/api/ai/metrics/recent`.

## backend pointers
- Auth/JWT: POST /api/token, /api/token/refresh. OAuth (Google) scaffold at /api/oauth/google/*.
- RLS session: `accounts.middleware.RLSSessionMiddleware` sets Postgres GUCs (current_user_id/org_id/role).
- Proposals: `proposals/views.py` (org membership enforced), `proposals/models.py` (JSONB + shared_with).
- AI: `ai/views.py` uses provider abstraction `ai/provider.py`. Default is a composite provider: GPT-5 plans/writes, Gemini formats/polishes. Inputs sanitized. File references from uploads (`file_refs`) are accepted on write/revise/format and threaded to providers. Optional async via Celery: set `AI_ASYNC=1` and `REDIS_URL`; POST endpoints return `{job_id}` and poll `GET /api/ai/jobs/{id}`.
  - Providers add a deterministic context block when `file_refs` are present: the output appends a `[context:sources]` section with `- name: <ocr snippet>` lines (snippets trimmed). Tests cover this behavior.
- Exports: `exports/utils.py`, `exports/views.py` (async optional via `EXPORTS_ASYNC=1`).
- Billing: `billing/views.py` (usage/checkout/portal/cancel/resume), `billing/webhooks.py`, `billing/quota.py`, `billing/models.py`.
- Files/OCR: `files/views.py` supports txt/docx extraction; PDFs via pdfminer; optional image OCR via pytesseract/PIL behind `OCR_IMAGE=1`; optional PDF OCR when `OCR_PDF=1` and `ocrmypdf` binary present. SPA surfaces OCR previews and passes `file_refs` to AI endpoints.
- RLS policies: SQL applied in `db_policies/migrations/0001_rls.py` (+ fixes in 0002). Postgres-only tests in `db_policies/tests/test_rls_policies.py` (skipped on SQLite).
 - Security headers/CSP: `app/middleware.py` sets CSP and other headers. Allow extra hosts via `CSP_SCRIPT_SRC`, `CSP_STYLE_SRC`, `CSP_CONNECT_SRC` (comma-separated, no quotes; 'self' auto-added).

## frontend pointers
- Router with base path from Vite; RequireAuth + RequireOrg guards; NotFound route. See `web/src/main.jsx` and `web/src/config.ts`.
- Keep markup minimal; no inline styles (see `docs/design_system.md`).
 - Vite config: no source maps in prod, hashed file names, console/debugger dropped; Umami optional via `VITE_UMAMI_*`.
 - Dev-only UI prompts behind `VITE_UI_EXPERIMENTS`.
 - Test-mode guards: dev-time base-path self-correction is disabled during unit tests; `safeOpenExternal` always calls `window.open` in tests to satisfy jsdom.
 - Router base: SPA mounts under `/app` (configurable via `VITE_ROUTER_BASE`); asset base served at `/static/app/` (`VITE_BASE_URL`).

## quotas and plans
- Defaults: QUOTA_FREE_ACTIVE_CAP=1; QUOTA_PRO_MONTHLY_CAP=20; QUOTA_PRO_PER_SEAT=10; enterprise optional cap.
- Effective Pro cap: seats * QUOTA_PRO_PER_SEAT + extras (credited via invoice webhook to `ExtraCredits`).
- Enforcement: middleware blocks POST /api/proposals when over cap (402 + X-Quota-Reason); creation permission `billing.permissions.CanCreateProposal`.

## what to implement or extend
- Proposals CRUD exists and is scoped; keep membership checks aligned with RLS.
- Stripe lifecycle: cancel/resume endpoints done; webhook handlers robust; enforcement command marks canceled after period end. Add tests for immediate-cancel and failed payment grace.
  - Immediate-cancel and failed-payment grace tests are present and should remain green.
- AI: provider abstraction in place; real providers wired via env. Celery offload optional (`AI_ASYNC=1`).
- OCR: both image and PDF OCR paths implemented; UI surfaces OCR previews.
- RLS: baseline Postgres tests exist; expand coverage and document least-privileged DB user.
- Analytics: AIMetric v2 present (proposal_id, section_id). Keep logging on new AI surfaces; extend summary safely.
- Hardening: keep CSP tight; update allow-lists only when needed; maintain no-source-maps and console stripping.

## how to run
- Local tasks (VS Code tasks):
  - API: migrate, runserver (DEBUG), lint (ruff), test (per-app selection).
  - Web: dev, lint.
- Smoke endpoints once up: GET /healthz; GET /api/usage (with/without X-Org-ID); POST /api/stripe/webhook (DEBUG only).
 - Async (optional): run a Celery worker with the same image. Requires `REDIS_URL`. Exports async via `EXPORTS_ASYNC=1`; AI async via `AI_ASYNC=1`.

## testing
- Run Django tests per app: `python manage.py test -v 2 <app>` to avoid discovery collisions.
- Exports determinism covered (md/pdf/docx). Billing seats/extras tests present. RLS tests exist (skipped unless Postgres).
 - AI metrics tests cover proposal/section capture and summary aggregates.
 - CI hardening ensures web/dist has no source maps or console strings; images audited for stray docs/tests/maps.
 - Web tests with Vitest/jsdom rely on test-mode guards for navigation; avoid direct location changes in unit tests.

## quick refs
- Quota service: `api/billing/quota.py`; middleware: `api/billing/middleware.py`.
- Usage/billing endpoints: `api/billing/views.py`.
- RLS GUC middleware: `api/accounts/middleware.py`.
- Models: `api/proposals/models.py`, `api/billing/models.py`, `api/orgs/models.py`.
 - AI provider/tasks: `api/ai/provider.py`, `api/ai/views.py`, `api/ai/tasks.py`.
 - Exports async: `api/exports/tasks.py` (if present), `api/exports/views.py`.
 - Files/OCR: `api/files/views.py`.
 - Security middleware: `api/app/middleware.py`; CSP env allow-lists in `api/app/settings.py`.
 - Vite config: `web/vite.config.ts` (prod obfuscation), ESLint: `web/eslint.config.js` (JS/JSX scoped lint currently).
 - SPA bases: Router base in code (`VITE_ROUTER_BASE`), asset base in Vite config (`VITE_BASE_URL`).
 - Env templates: `.env.example`, `.env.coolify.example`; installation: `docs/install_guide.md`.

## environment keys (high impact)
- OAuth (Google): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI, GOOGLE_JWKS_URL, GOOGLE_ISSUER
- Core: SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL, REDIS_URL, PUBLIC_BASE_URL
- CORS/CSRF: CORS_ALLOW_ALL, CORS_ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS, CSRF_TRUSTED_ORIGINS
- Security: SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS, SECURE_HSTS_INCLUDE_SUBDOMAINS, SECURE_HSTS_PRELOAD, SECURE_REFERRER_POLICY, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SESSION_COOKIE_SAMESITE, CSRF_COOKIE_SAMESITE
 - CSP allow-lists: CSP_SCRIPT_SRC, CSP_STYLE_SRC, CSP_CONNECT_SRC (comma-separated, no quotes); CSP_ALLOW_INLINE_STYLES=1 to temporarily include 'unsafe-inline' in style-src (default off)
- Async: EXPORTS_ASYNC, AI_ASYNC, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_ALWAYS_EAGER
- SPA: VITE_BASE_URL, VITE_API_BASE, VITE_UMAMI_WEBSITE_ID, VITE_UMAMI_SRC, VITE_UI_EXPERIMENTS
 - SPA router base: VITE_ROUTER_BASE (default '/app')
- OAuth: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI, GOOGLE_JWKS_URL, GOOGLE_ISSUER
- Email: INVITE_SENDER_DOMAIN, EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, FRONTEND_INVITE_URL_BASE
- Billing: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_PRO_MONTHLY, PRICE_PRO_YEARLY, PRICE_ENTERPRISE_MONTHLY, PRICE_BUNDLE_1, PRICE_BUNDLE_10, PRICE_BUNDLE_25
- Uploads: FILE_UPLOAD_MAX_MEMORY_SIZE, ALLOWED_UPLOAD_EXTENSIONS
- Quotas: QUOTA_FREE_ACTIVE_CAP, QUOTA_PRO_MONTHLY_CAP, QUOTA_PRO_PER_SEAT, QUOTA_ENTERPRISE_MONTHLY_CAP
- OCR: OCR_IMAGE, OCR_PDF
- AI provider keys: AI_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY
 - Orgs/Invites: ORG_INVITE_TTL_DAYS, ORG_INVITES_PER_HOUR, APP_HOSTS

## CI and release safety
- Web build must not contain source maps or console/debugger strings.
- Docker images must exclude docs/tests/maps and optional source stripping can be enabled via `STRIP_PY=1` build arg for API.
- Workflows audit images and dist artifacts; keep them green before merging.
 - Landing server: reject untrusted Host headers; keep CSP allow-lists minimal and environment-driven.

Consistency rule: If a doc conflicts with code, trust the code and update this file and bring the inconsistent doc up to date. After significant changes, reflect them in `Todo.md` as well.