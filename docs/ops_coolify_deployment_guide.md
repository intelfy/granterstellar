[[AI_CONFIG]]
FILE_TYPE: 'DEPLOYMENT_GUIDE'
INTENDED_READER: 'LOW_TECHNICAL_HUMAN_OPERATOR'
PURPOSE: ['Provide step-by-step deployment instructions', 'Ensure correct environment variable configuration', 'Facilitate easy setup with Coolify and Traefik', 'Ensure foolproof deployment process']
PRIORITY: 'CRITICAL'
[[/AI_CONFIG]]

# Granterstellar — Install & Coolify Deployment Guide (idiot‑proof)

This guide tells you exactly what to click and what to paste to deploy Granterstellar using Coolify (with Traefik). No Linux or Docker knowledge required.

What you’ll get

- One app that serves everything on port 8000: API, SPA under /app, static landing at /.
- Optional: a separate “Landing” app for a waitlist form (port 5173). You can skip this.
- Managed Postgres (required) and Redis (optional unless you want async jobs).
- SPA performance: route-level code splitting, idle-time preloads for likely next pages, and optional Web Vitals logging.
- Lean image: `.dockerignore` prunes markdown/docs/tests/source maps from build context.

Before you begin

- You have a Coolify instance reachable at a domain, with Traefik enabled.
- You pointed your DNS (A/AAAA) for your chosen app domain to Coolify.
- You can connect this GitHub repo to Coolify.

Recommended domains

- Test: <https://grants.intelfy.dk>
- Production: <https://forgranted.io>

Routes (defaults)

- / → landing page (static files bundled in the API image)
- /app → the React SPA
- /static/app → SPA assets (JS/CSS)
- /api/* → Django API
- /healthz and /api/healthz → health endpoints (plain text and JSON)

Key concepts (keep these defaults)

- Asset base: VITE_BASE_URL = /static/app/
- Router base: VITE_ROUTER_BASE = /app
- App hosts: APP_HOSTS = comma‑separated hostnames that should redirect / → /app
- Invite acceptance: SPA surfaces a global invite banner when an invite token is in the URL (selectors in docs/style-docs.md).
 - Distinct JWT signing key: set `JWT_SIGNING_KEY` different from `SECRET_KEY` (enforced by forthcoming doctor script) to allow rotation without invalidating Django internals.

Step 1 — Create PostgreSQL in Coolify

1) New Resource → Application → pick a PostgreSQL 16 template.
2) Name it “granterstellar-postgres”.
3) Set database name, username, password. Click Deploy.
4) Copy the internal connection URL it shows. You will paste it as DATABASE_URL later.

Step 2 — Create Redis in Coolify (optional but recommended)

1) New Resource → Application → pick Redis 7.
2) Name it “granterstellar-redis”.
3) Deploy and copy the internal Redis URL (e.g., redis://redis:6379/0). You will paste it as REDIS_URL later.

Step 3 — Deploy the App (API + SPA)

1) New Resource → Application → “Dockerfile”.
2) Repo: this repo; Branch: main; Context: repo root; Dockerfile path: api/Dockerfile.
3) Domain: your app domain (e.g., app.example.com). Traefik will handle HTTPS.
4) Internal Port: 8000. Healthcheck path: /healthz.
5) Storage: add volumes mounted at /app/media (uploads/exports) and optionally /backups (DB dumps for external backup tools).
6) Environment → paste the template below and fill values (keep syntax exactly):

Paste this into Coolify → Environment

```env
# Required
SECRET_KEY=change-me-to-a-long-random-string
DEBUG=0
ALLOWED_HOSTS=app.example.com,localhost,127.0.0.1
PUBLIC_BASE_URL=https://app.example.com

# Database/Cache
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
REDIS_URL=redis://HOST:6379/0

# CORS/CSRF (comma-separated origins; full https origins)
CORS_ALLOW_ALL=0
CORS_ALLOWED_ORIGINS=https://app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com

# SPA bases (keep defaults)
VITE_BASE_URL=/static/app/
VITE_API_BASE=/api
VITE_ROUTER_BASE=/app

# Optional SPA analytics (Umami)
VITE_UMAMI_WEBSITE_ID=
VITE_UMAMI_SRC=
VITE_UI_EXPERIMENTS=0
VITE_WEB_VITALS=0

# Security headers (comma-separated, no quotes; 'self' is auto-added)
CSP_SCRIPT_SRC=
CSP_STYLE_SRC=
CSP_CONNECT_SRC=
# Temporary escape hatch for inline CSS; default off (0)
CSP_ALLOW_INLINE_STYLES=0

# App hosts that should redirect / → /app (comma-separated hostnames)
APP_HOSTS=

# Async (optional; set to 1 only if you run a Celery worker)
EXPORTS_ASYNC=0
AI_ASYNC=0
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

# JWT (optional)
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7
JWT_SIGNING_KEY=

# DRF throttles (optional)
DRF_THROTTLE_USER=100/min
DRF_THROTTLE_ANON=20/min
DRF_THROTTLE_LOGIN=10/min
# DRF_THROTTLE_LOGIN controls a scoped rate limit for the JWT login endpoint (/api/token),
# enforced by ScopedRateThrottle with scope="login" to deter brute‑force attempts.

# Uploads & OCR (optional)
FILE_UPLOAD_MAX_BYTES=10485760
# Django in-memory threshold; also used as fallback when FILE_UPLOAD_MAX_BYTES is unset
FILE_UPLOAD_MAX_MEMORY_SIZE=10485760
TEXT_EXTRACTION_MAX_BYTES=8388608
ALLOWED_UPLOAD_EXTENSIONS=pdf,png,jpg,jpeg,docx,txt
OCR_IMAGE=0
OCR_PDF=0

# Optional virus scan hook (command template; {path} placeholder is replaced with file path)
VIRUSSCAN_CMD=
VIRUSSCAN_TIMEOUT_SECONDS=10

# Quotas
QUOTA_FREE_ACTIVE_CAP=1
QUOTA_PRO_MONTHLY_CAP=20
QUOTA_PRO_PER_SEAT=10
QUOTA_ENTERPRISE_MONTHLY_CAP=

# Failed payment grace window (days)
FAILED_PAYMENT_GRACE_DAYS=3

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OAUTH_REDIRECT_URI=https://app.example.com/api/oauth/google/callback
GOOGLE_JWKS_URL=https://www.googleapis.com/oauth2/v3/certs
GOOGLE_ISSUER=https://accounts.google.com

# --- OAuth (GitHub & Facebook) notes (uncomment and set if you enable these providers) ---
# GITHUB_CLIENT_ID=
# GITHUB_CLIENT_SECRET=
# GITHUB_REDIRECT_URI=
# FACEBOOK_APP_ID=
# FACEBOOK_APP_SECRET=
# FACEBOOK_REDIRECT_URI=
# FACEBOOK_API_VERSION=v12.0
# In DEBUG without secrets, callbacks accept an `email` parameter for local testing.
# Ensure VITE_API_BASE points to the API origin.

# Email for invites (SMTP)
INVITE_SENDER_DOMAIN=mg.yourdomain.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=postmaster@mg.yourdomain.com
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=1
# Invite link base (should point to SPA)
FRONTEND_INVITE_URL_BASE=https://app.example.com/app

# Stripe (payments)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
PRICE_PRO_MONTHLY=
PRICE_PRO_YEARLY=
PRICE_ENTERPRISE_MONTHLY=
PRICE_BUNDLE_1=
PRICE_BUNDLE_10=
PRICE_BUNDLE_25=

# AI providers (optional)
AI_PROVIDER=
OPENAI_API_KEY=
GEMINI_API_KEY=

Uploads cap enforcement

- The upload API enforces FILE_UPLOAD_MAX_BYTES as the hard cap. If unset, it falls back to FILE_UPLOAD_MAX_MEMORY_SIZE.
- TEXT_EXTRACTION_MAX_BYTES bounds parsing work for txt/docx/pdf.

Environment variables reference (what they do and why)

Host, routing, and origins

- ALLOWED_HOSTS: Server‑side safety. Comma‑separated hostnames the Django app will serve (protects against Host‑header spoofing). Must include your app domain.
- PUBLIC_BASE_URL: The external https URL of your app. Used for absolute links in emails and redirects.
- APP_HOSTS: Controls what happens when a user visits the root path “/”.
      - Purpose: On the hosts listed here, “/” will 301‑redirect to “/app” (the SPA). On other hosts, “/” serves the static landing page.
      - When to set: Add the hostnames where the SPA should be the home page.
      - When to leave out: Exclude your marketing/landing host if you want it to show the landing page at “/”.
      - Format: Comma‑separated hostnames (no scheme, no slashes). Examples:
         - Single app host: `APP_HOSTS=app.example.com`
         - Root domain SPA: `APP_HOSTS=forgranted.io`
         - Test/prod: `APP_HOSTS=grants.intelfy.dk,forgranted.io`
      - CORS_ALLOWED_ORIGINS / CSRF_TRUSTED_ORIGINS: Browser cross‑origin rules. List full origins (scheme + host, e.g., <https://app.example.com>) that can call the API/send cookies.
- VITE_BASE_URL / VITE_ROUTER_BASE: How the SPA is served and routed. Keep defaults unless you have a custom CDN.

 
Content Security Policy (CSP) allow‑lists

- Defaults: The app ships a strict CSP that only allows same‑origin resources. These envs extend, not replace, the defaults.
- Syntax: Comma‑separated URLs/hosts, no quotes. Do not include 'self' (it’s auto‑added).
- CSP_SCRIPT_SRC: Extra hosts you load scripts from (e.g., your analytics script host).
   - Example (Umami): `CSP_SCRIPT_SRC=https://analytics.example.com`
- CSP_STYLE_SRC: Extra style sources (e.g., a CSS CDN). Avoid 'unsafe-inline'.
   - Example: `CSP_STYLE_SRC=https://cdn.example.com`
- CSP_CONNECT_SRC: Where the browser is allowed to make XHR/fetch/WebSocket requests to.
   - Why it matters: Without listing a host here, the browser will block fetch() to that host even if the network is reachable.
   - You typically add your analytics collector or other third‑party APIs used directly from the browser.
   - Examples:
      - Umami collector: `CSP_CONNECT_SRC=https://analytics.example.com`
      - Multiple endpoints: `CSP_CONNECT_SRC=https://analytics.example.com,https://api.other.com`
   - Not needed for: Google OAuth redirects (top‑level navigation), server‑to‑server calls in Django.

Inline styles escape hatch

- CSP_ALLOW_INLINE_STYLES: Set to 1 to temporarily allow inline CSS by adding 'unsafe-inline' to style-src. Default is 0 (disabled), which is recommended for security.
   - Example: CSP_ALLOW_INLINE_STYLES=1 (use only as a short-term workaround while migrating styles to external CSS).
   - Upcoming: optional CSP reporting (`CSP_REPORT_URI`, `CSP_REPORT_ONLY=1`) for progressive tightening (see security_hardening.md once updated).


7) Build Arguments (optional): STRIP_PY=1 to obfuscate Python source in the image (enable for production later).
8) Deploy. After first deploy, run migrations:
   - Coolify → Your App → Commands → Run:
     - python manage.py migrate --noinput
     - python manage.py collectstatic --noinput
   - Optional: python manage.py createsuperuser
   - Optional (dev only): python manage.py seed_demo

Smoke test

- Visit <https://app.example.com/healthz> → ok
- Visit <https://app.example.com/app> → SPA loads
- Visit <https://app.example.com/api/usage> → JSON

Step 4 — Optional: Deploy a Celery worker (for async exports/AI)

1) New Resource → Application → “Dockerfile” (same repo, api/Dockerfile).
2) No domain. No internal port.
3) Copy the API app’s environment; set EXPORTS_ASYNC=1 and fill CELERY_* and REDIS URLs.
4) Command override: celery -A app.celery:app worker -l info
5) Deploy.

Step 5 — Optional: Landing (waitlist) app

If you want a separate waitlist page with double opt‑in via Mailgun:

1) New Resource → Application → “Dockerfile”; Context: repo root; Dockerfile: Dockerfile; Port: 5173; Healthcheck: /healthz.
2) Environment:
   - PUBLIC_BASE_URL=https://your-landing-domain
   - MAILGUN_DOMAIN=mg.yourdomain.com
   - MAILGUN_API_KEY=key-...
   - MAILGUN_API_HOST=api.mailgun.net (or api.eu.mailgun.net)
   - MAILGUN_LIST=waitlist@mg.yourdomain.com
   - NODE_ENV=production
   - ALLOW_HTTP_IN_PROD=1 (only when HTTPS is terminated by a reverse proxy like Traefik)
3) DNS for the landing domain should point to Coolify/Traefik.

Landing server HTTPS and throttling (when running standalone)

- The small Node landing server (`server.mjs`) can serve the static landing and waitlist endpoint by itself. In production it typically sits behind Traefik/Coolify with TLS termination.

- If you run it directly, you can enable HTTPS and tune resource guards via environment variables:
   - ENABLE_HTTPS=1: Start HTTPS when key/cert paths are provided.
   - HTTPS_KEY_PATH, HTTPS_CERT_PATH: File paths to your TLS key and certificate.
   - ALLOW_HTTP_IN_PROD=1: Allow HTTP mode even with NODE_ENV=production (use only behind a TLS proxy).
   - STATIC_FS_CONCURRENCY: Max concurrent static file streams (default 50).
         - STATIC_RATE_LIMIT_MAX: Per‑IP GET/HEAD rate limit window cap (default 300 per 5 minutes).

- When running behind Traefik, keep HTTP mode; TLS is terminated at the proxy. Security headers and CSP are still set by the server.

- Umami analytics injection is validated: src must be https and end with `/script.js`, and website id is attribute‑escaped.
   - The SPA also supports Umami via VITE_UMAMI_* with CSP allow‑lists; the landing server enforces strict validation and CSP.

Providers setup (copy‑paste friendly)

Stripe
 
1) Dashboard → Developers → API keys → set STRIPE_SECRET_KEY.

2) Developers → Webhooks → Add endpoint: <https://app.example.com/api/stripe/webhook>; copy Signing secret → STRIPE_WEBHOOK_SECRET.
3) Products/Prices → create prices; paste IDs into PRICE_* envs.
4) Billing endpoints (server): /api/billing/checkout, /api/billing/portal, /api/billing/cancel, /api/billing/resume.
   - Checkout returns `{ url, session_id }`. Use `url` to redirect. `session_id` can be used client-side as needed.
   - In DEBUG, if `price_id` is omitted and Stripe is configured, a minimal test Product/Price may be auto-created for convenience.
   - Immediate cancel: POST {"immediate": true} to /api/billing/cancel.
5) Grace window: FAILED_PAYMENT_GRACE_DAYS controls Pro access during past_due.

Google OAuth
 
1) Google Cloud → OAuth client: web app. Authorized redirect URI: <https://app.example.com/api/oauth/google/callback>; Authorized JS origin: <https://app.example.com>.
2) Copy client ID/secret → GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET and set OAUTH_REDIRECT_URI.
3) DEBUG shortcut: in development without GOOGLE_CLIENT_SECRET, POST to `/api/oauth/google/callback` with form fields `code=x&email=you@example.com` to get tokens.

Umami analytics (SPA)
 
1) Set VITE_UMAMI_WEBSITE_ID and VITE_UMAMI_SRC. Also add the host to CSP_SCRIPT_SRC and CSP_CONNECT_SRC.

Quotas
 
- QUOTA_FREE_ACTIVE_CAP=1, QUOTA_PRO_MONTHLY_CAP=20, QUOTA_PRO_PER_SEAT=10, QUOTA_ENTERPRISE_MONTHLY_CAP= (empty for unlimited).
- Check with GET /api/usage. On quota block, POST /api/proposals returns 402 with X-Quota-Reason.

AI endpoints and gating
 
- Scoping: Pass `X-Org-ID: <org_id>` to apply AI usage and subscription checks to an organization. Omit to use the personal scope.
- Gating (production): `/api/ai/write`, `/api/ai/revise`, and `/api/ai/format` require a Pro/Enterprise plan in the chosen scope. Free tier requests are blocked with HTTP 402 and `X-Quota-Reason: ai_requires_pro`.
- DEBUG bypass: When `DEBUG=1`, AI endpoints allow requests regardless of plan (useful for local development and tests).
- Async (optional): With `AI_ASYNC=1` and Celery configured, AI calls return `{job_id}` and progress can be polled via `/api/ai/jobs/{id}`.

Admin/operations
 
- Add Coolify Scheduled Command (daily) to run: `python manage.py enforce_subscription_periods`
- Backups: two options
   1) Enable managed Postgres backups in Coolify (recommended if available). Test restore.
   2) Self-managed dumps: mount a persistent volume at /backups and run the provided script daily.
       - Script: scripts/pg_dump_daily.sh (expects DATABASE_URL)
       - Compose example includes a 'backup' service that runs this daily and writes gzipped SQL files under /backups.
       - Point Duplicati (or your backup tool) at the /backups path to offload copies off-site.

Media (uploads) backup
 
- Include the /app/media volume in your backup strategy in addition to the database.
- Simple snapshots: schedule a nightly job to archive MEDIA_ROOT using the helper script.
      - Script (in repo): `scripts/media_backup.sh` (defaults SOURCE=/app/media, DEST=/backups/media)
      - Mount a persistent volume or host path at /backups, and schedule a Coolify command:
         - `bash scripts/media_backup.sh`
      - Retention: set `RETAIN_DAYS` env on the app to control how many days to keep (default 30).
- Alternative: rsync/object storage sync
      - If you have an object store (e.g., S3), run a nightly sync of /app/media to a bucket path (server-side lifecycle keeps versions).
      - Ensure server-side encryption and lifecycle rules (30–90 days) per your policy.
- Restore procedure (snapshot tar.gz):
   1) Stop app or put in maintenance.
   2) Extract the desired archive into MEDIA_ROOT:
       - tar -xzf /backups/media/media_HOST_YYYY-MM-DD_HHMMSS.tar.gz -C /app/media
   3) Verify file ownership/permissions match the app user.
   4) Start app; spot-check downloads and exports.
- Hygiene & safety checks:
      - Run `python manage.py list_orphaned_media` monthly and investigate large orphan counts.
      - Consider excluding ephemeral export caches if you add any non-persistent temp dirs later.

Uploads behavior and tuning
 
- Oversized uploads: when a file exceeds FILE_UPLOAD_MAX_BYTES, the API returns HTTP 413 with `{ "error": "file_too_large", "limit": <bytes> }`.
- Signature/MIME checks: png/jpg/jpeg/pdf/docx are validated with magic bytes and MIME guess; mismatches return 400 (`mismatched_signature` or `mismatched_content_type`).
- Extraction limits: text/parse work is bounded by TEXT_EXTRACTION_MAX_BYTES to avoid heavy CPU/memory usage.
- Optional virus scan: set VIRUSSCAN_CMD to a command template (use `{path}` placeholder). Non‑zero exit is treated as infected (400 `infected`); invocation errors fail closed (400 `scan_error`).

Common mistakes (and fixes)
 
- 403/CSRF or CORS errors: ensure CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS include your https origin, no trailing slashes.
- 400 on Google OAuth: OAUTH_REDIRECT_URI must exactly match Google console entry; use https.
- Stripe webhook 401/400: set STRIPE_WEBHOOK_SECRET in production; in DEBUG webhooks accept unsigned JSON.
- SPA not loading assets: keep VITE_BASE_URL=/static/app/ (matches Dockerfile copy path and Django static path).
- Invites email not sent: configure EMAIL_* SMTP settings and INVITE_SENDER_DOMAIN; check provider logs.
 - JWT SIGNING issues: ensure `JWT_SIGNING_KEY` is set and not equal to `SECRET_KEY`; rotate signing key by overlapping validity (short access tokens) and updating refresh logic carefully.

## Run RLS (Postgres) tests locally

Row-Level Security tests only run against PostgreSQL and are skipped on SQLite. To run them locally:

- Start a Postgres instance you can connect to (Docker, local, or managed).
- Set DATABASE_URL to your Postgres connection (the test runner will use it).
- Apply migrations to that database before running tests.

Two easy options:

1) Using VS Code task (recommended)
   - Ensure DATABASE_URL is set in your shell or the workspace environment.
   - Run task: “API: test (RLS on Postgres)”.

2) Using the Django test runner directly
   - From the repo root:
     - cd api
     - DEBUG=1 SECRET_KEY=test DATABASE_URL=postgres://USER:PASS@HOST:5432/DB .venv/bin/python manage.py migrate
     - DEBUG=1 SECRET_KEY=test DATABASE_URL=postgres://USER:PASS@HOST:5432/DB .venv/bin/python manage.py test -v 2 db_policies.tests

Notes
 
- If connection.vendor is not "postgresql", the suite is skipped by design.
- Keep a disposable database for tests; they create/tear down data.

## Least-privileged DB user (recommended)

For production, use a dedicated Postgres role without BYPASSRLS and with only CRUD on application tables. See `docs/rls_postgres.md` for SQL and guidance.

Last updated: 2025-09-01

## Staging verification checklist — Stripe promos/coupons

- Create a product and promotion code or coupon in Stripe (test mode).
- Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` (test keys) in staging.
- Create prices and wire IDs to `PRICE_*` envs.
- Start a checkout with a promo code; complete payment in Stripe’s test UI.
- Verify in app:
   - `/api/usage` reflects `subscription.discount` (percent/amount and duration).
   - Quotas remain correct (no unintended unlimited effects).
      - Webhook events apply without errors and idempotently on retry.
   - Run the customer portal; check that cancel/resume toggles persist via webhooks.