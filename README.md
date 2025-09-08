[[AI_CONFIG]]
FILE_TYPE: 'MARKETING_README'
INTENDED_READER: 'NON_TECHNICAL_PUBLIC'
PURPOSE: ['Provide an overview of the application', 'Highlight key features and technologies', 'Guide users to relevant documentation', 'Facilitate understanding for non-technical stakeholders']
PRIORITY: 'HIGH'
[[/AI_CONFIG]]

# Granterstellar — Full App Guide · Coolify + Traefik

This README covers the full application (SPA + API + DB). For the docs index, see `docs/README.md`. For install and env details, see `docs/ops_coolify_deployment_guide.md` (formerly install_guide).

Contributing? See `CONTRIBUTING.md` for local tasks, lint/tests, and conventions.

## Overview

- Product: Guided grant-writing SaaS with AI-assisted authoring, JSONB-backed proposal storage, and deterministic exports (md/docx/pdf).
- Architecture: Monolith with React SPA and Django API; Postgres; optional Redis/Celery; deployed via Coolify behind Traefik.
- Data: Identity/billing in relational tables; proposal content in JSONB; RLS enforced via DB session variables.

## Repo layout

- `api/` — Django project (accounts, orgs, proposals, billing, ai, exports, files)
- `web/` — React SPA (Vite)
- `api/Dockerfile` — API image (bundles SPA build + landing via WhiteNoise)
- `docker-compose.yml` / `app-compose.yml` — local dev stacks
- `docs/` — install guide, design rules, exports async, RLS notes

## Technology

- Backend: Django + DRF, Postgres, optional Celery/Redis
- Frontend: React (Vite)
- AI: Provider abstraction (GPT-5 plans/writes, Gemini formats/polishes) with plan gating, per‑minute limiter, and deterministic single-write debug limiter (see `docs/ai_rate_limiting.md`).
- Billing: Stripe subscriptions + bundles + customer portal/webhooks
- Exports: Canonical Markdown → DOCX/PDF, deterministic outputs/checksums
  - Design & guarantees: see `docs/deterministic_exports.md`
  - Rate limiting & gating: see `docs/ai_rate_limiting.md`
- OCR: PDFs via pdfminer; optional image OCR via pytesseract/PIL; optional PDF OCR via `ocrmypdf` (behind flags)

## Deployment topology

Single image recommended:

- SPA routes under `/app`; SPA static assets under `/static/app`.
- API serves landing at `/` and SPA index for `/app` routes; `/api/*` for API; static/media via WhiteNoise.
- Optional host-aware redirect: requests to configured app hosts at `/` redirect to `/app` (set `APP_HOSTS` as a comma-separated list of hostnames).

See `docs/ops_coolify_deployment_guide.md` for CSP allow-lists, domains, and environment examples. Test domain: <https://grants.intelfy.dk>; projected production: <https://forgranted.io>. Analytics host: <https://data.intelfy.dk>.

Image hygiene: build context excludes markdown/docs/tests/source maps via `.dockerignore` to minimize image surface and speed builds.

## Local development (no Docker)

Use the included VS Code tasks:

- API: “API: runserver (DEBUG)”
- Web: “Web: dev”
- Both: “Dev: API + Web”
- Optional async: start Redis (e.g., brew) and run “API: celery worker”
- Seed demo: “API: seed demo”

The SPA calls `/api` by default. When running API separately, set `VITE_API_BASE` to your API URL.

### Stripe testing (local)

- Start the API (DEBUG) and the web dev server via VS Code tasks.
- Run Stripe CLI to forward webhooks to your API:
  - `stripe listen --print-secret --forward-to http://127.0.0.1:8000/api/stripe/webhook`
  - Paste the printed signing secret into `STRIPE_WEBHOOK_SECRET` for the API task.
- Create a test Product/Price in your Stripe test dashboard (or via SDK).
- Call POST `/api/billing/checkout` with `{ price_id }`.
  - Response includes `{ url, session_id }` for Stripe Checkout.
  - In DEBUG, if `price_id` is omitted and Stripe is configured, a minimal test Product/Price may be auto-created for convenience.

Discounts & promotions

- The API persists active discounts from Stripe on the subscription and returns them on `/api/usage`.
- When Stripe removes a discount (subscription.updated with `discount: null`), the webhook clears it; the UI hides the promo banner automatically.
- In local dev/tests, after opening Checkout, the Billing view refreshes usage to reflect changes faster. In production, webhooks drive consistency.

## SPA routing and base paths

- Asset base: `VITE_BASE_URL` (default `/static/app/`) controls where built assets are served.
- Router base: `VITE_ROUTER_BASE` (default `/app`) controls the SPA route prefix.
- During dev, refreshes at bare paths are auto-corrected to include the router base.

Environment, security, and operations

- For a copy‑paste environment template and full explanations (CSP, uploads, quotas, OAuth, Stripe, async), see `docs/ops_coolify_deployment_guide.md`.
- For deployment hardening tips, see `docs/security_hardening.md`.
- For ops triage and health checks, see `docs/ops_runbook.md`.

## CI, tests, and lint

- API: run Django tests per app (e.g., `python manage.py test -v 2 accounts`); determinism tests verify exports.
- Web: ESLint (flat config) and Vitest.
- Build hardening: no source maps in prod; console/debugger stripped; CSP enforced.
- Dependency/security: optional `scripts/deps_audit.sh` runs pip-audit + npm audit + SBOM generation when supporting tools are installed (non-fatal if missing).
- Automated audits: GitHub Actions workflow (`.github/workflows/deps_audit.yml`) runs weekly and on PRs – executes pip-audit (JSON), Bandit, npm audit (--json), and CycloneDX SBOM generation for Python & JS. Artifacts (reports + SBOMs) are uploaded; the job fails on HIGH/CRITICAL vulns (precise severity parsing WIP). Use the local `scripts/deps_audit.sh` for ad-hoc verification.

## Health & readiness endpoints

The API exposes lightweight JSON probes:

- `GET /api/health` — liveness (always 200 if process/thread responding)
- `GET /api/ready` — readiness (verifies DB connectivity and cache availability). On failure returns a standardized error payload:

```json
{
  "error": { "code": "not_ready", "message": "database_unreachable", "version": 1, "meta": { /* optional */ } }
}
```

Use `/api/health` for basic uptime monitors and `/api/ready` for deploy rollouts / load balancer target health. The readiness endpoint purposefully exercises a trivial DB query; extend it if future dependencies (e.g. external vector store) become launch‑critical.

## AI gating & rate limiting (summary)

## Performance tweaks

Added early font + script preload hints on landing (`index.html`) and module/font preloads in SPA (`web/index.html`). Future step: capture before/after Web Vitals (LCP/TTI) once staging deployed; tighten budgets afterward.

Centralized in a decorator (`ai_protected`) wrapping AI endpoints. Layers: plan gating → deterministic single‑write debug guard → cache fast path → DB authoritative count. See `docs/ai_rate_limiting.md` for deep dive (now updated with decorator + cache fast path details).

## Notes

- Design: keep markup minimal; avoid inline styles (see `docs/design_system.md`).
- RLS: Postgres row policies tested; middleware sets session GUCs.

## Endpoints & quick refs

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
- Stripe: run a `stripe listen --print-secret --forward-to http://127.0.0.1:8000/api/stripe/webhook` session for local webhook parity; paste the secret into the API task env.
