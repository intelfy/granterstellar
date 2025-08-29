# Granterstellar — Full App Guide · Coolify + Traefik

This README covers the full application (SPA + API + DB). For the docs index, see `docs/README.md`. For install and env details, see `docs/install_guide.md`.

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
- AI: Provider abstraction (GPT-5 plans/writes, Gemini formats/polishes)
- Billing: Stripe subscriptions + bundles + customer portal/webhooks
- Exports: Canonical Markdown → DOCX/PDF, deterministic outputs/checksums
- OCR: PDFs via pdfminer; optional image OCR via pytesseract/PIL; optional PDF OCR via `ocrmypdf` (behind flags)

## Deployment topology
Single image recommended:
- SPA routes under `/app`; SPA static assets under `/static/app`.
- API serves landing at `/` and SPA index for `/app` routes; `/api/*` for API; static/media via WhiteNoise.
- Optional host-aware redirect: requests to configured app hosts at `/` redirect to `/app` (set `APP_HOSTS` as a comma-separated list of hostnames).

See `docs/install_guide.md` for CSP allow-lists, domains, and environment examples. Test domain: https://grants.intelfy.dk; projected production: https://forgranted.io. Analytics host: https://data.intelfy.dk.

## Local development (no Docker)
Use the included VS Code tasks:
- API: “API: runserver (DEBUG)”
- Web: “Web: dev”
- Both: “Dev: API + Web”
- Optional async: start Redis (e.g., brew) and run “API: celery worker”
- Seed demo: “API: seed demo”

The SPA calls `/api` by default. When running API separately, set `VITE_API_BASE` to your API URL.

## SPA routing and base paths
- Asset base: `VITE_BASE_URL` (default `/static/app/`) controls where built assets are served.
- Router base: `VITE_ROUTER_BASE` (default `/app`) controls the SPA route prefix.
- During dev, refreshes at bare paths are auto-corrected to include the router base.

## Environment keys (high impact)
- OAuth (Google): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `GOOGLE_JWKS_URL`, `GOOGLE_ISSUER`
- Core: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `PUBLIC_BASE_URL`
- CORS/CSRF: `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL`, `CSRF_TRUSTED_ORIGINS`
- Async: `EXPORTS_ASYNC`, `AI_ASYNC`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- SPA: `VITE_BASE_URL` (default `/static/app/`), `VITE_ROUTER_BASE` (default `/app`), `VITE_API_BASE`
- Analytics: `VITE_UMAMI_WEBSITE_ID`, `VITE_UMAMI_SRC` (e.g., https://data.intelfy.dk/script.js)
- Email: `INVITE_SENDER_DOMAIN`, SMTP vars, `FRONTEND_INVITE_URL_BASE` (use `https://<domain>/app`)
- Billing: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, price IDs; `FAILED_PAYMENT_GRACE_DAYS`
- Quotas: `QUOTA_FREE_ACTIVE_CAP`, `QUOTA_PRO_MONTHLY_CAP`, `QUOTA_PRO_PER_SEAT`, `QUOTA_ENTERPRISE_MONTHLY_CAP`
- OCR: `OCR_IMAGE`, `OCR_PDF`
- CSP: `CSP_SCRIPT_SRC`, `CSP_STYLE_SRC`, `CSP_CONNECT_SRC` (comma-separated; `'self'` auto-added)
- Orgs/Invites: `ORG_INVITE_TTL_DAYS` (invite expiry, days), `ORG_INVITES_PER_HOUR` (per-org rate limit), `APP_HOSTS` (hosts where `/` redirects to `/app`).

Environment variables — quick reference
- APP_HOSTS: Comma‑separated hostnames where visiting `/` should 301‑redirect to the SPA at `/app`. Leave empty to serve the static landing at `/`. Example: `APP_HOSTS=forgranted.io`.
- CSP_CONNECT_SRC: Extra hosts the browser may call via fetch/XHR/WebSockets. Needed for analytics collectors or third‑party APIs used from the SPA. Example: `CSP_CONNECT_SRC=https://analytics.example.com`.
- VITE_BASE_URL / VITE_ROUTER_BASE: Keep defaults (`/static/app/` and `/app`) unless you customize CDN/routing.
- FAILED_PAYMENT_GRACE_DAYS: Number of days Pro features remain available when Stripe marks a subscription `past_due`.
- PRICE IDs: `PRICE_PRO_MONTHLY`, `PRICE_PRO_YEARLY`, `PRICE_ENTERPRISE_MONTHLY`, and optional bundles `PRICE_BUNDLE_1`, `PRICE_BUNDLE_10`, `PRICE_BUNDLE_25`.
- JWT overrides: `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `JWT_SIGNING_KEY`.
- Upload constraints: `FILE_UPLOAD_MAX_MEMORY_SIZE`, `ALLOWED_UPLOAD_EXTENSIONS`.
- DRF throttles: `DRF_THROTTLE_USER`, `DRF_THROTTLE_ANON`.

See `.env.example` and `.env.coolify.example`.

## CI, tests, and lint
- API: run Django tests per app (e.g., `python manage.py test -v 2 accounts`); determinism tests verify exports.
- Web: ESLint (flat config) and Vitest.
- Build hardening: no source maps in prod; console/debugger stripped; CSP enforced.

## Notes
- Design: keep markup minimal; avoid inline styles (see `docs/design_system.md`).
- RLS: Postgres row policies tested; middleware sets session GUCs.
- Optional legacy landing: if you need a separate marketing-only landing, see `docs/install_guide.md` (optional step).

## Landing server (static) — HTTPS and throttling
The small Node landing server (`server.mjs`) serves the static landing and waitlist endpoint when used standalone. In production it typically sits behind Traefik/Coolify with TLS termination. If you run it directly, you can enable HTTPS and tune resource guards:

- ENABLE_HTTPS=1: Start HTTPS when key/cert paths are provided.
- HTTPS_KEY_PATH, HTTPS_CERT_PATH: File paths to your TLS key and certificate.
- STATIC_FS_CONCURRENCY: Max concurrent static file streams (default 50).
- STATIC_RATE_LIMIT_MAX: Per‑IP GET/HEAD rate limit window cap (default 300 per 5 minutes).

Example (local self‑signed certs):

```
ENABLE_HTTPS=1 \
HTTPS_KEY_PATH=./local.key \
HTTPS_CERT_PATH=./local.crt \
STATIC_FS_CONCURRENCY=100 \
node server.mjs
```

Notes:
- When running behind Traefik, leave HTTP mode; TLS is terminated at the proxy. Security headers and CSP are still set by the server.
- Umami analytics injection is strictly validated: src must be https and end with `/script.js`, and website id is attribute‑escaped.
