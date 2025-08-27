# Granterstellar — Full App Guide (MVP) · Coolify + Traefik

This is the working README for the full application (SPA + API + DB), optimized for deployment on Coolify behind Traefik. It complements the temporary landing page.

## Overview
- What: Guided grant-writing SaaS with AI-assisted authoring, JSONB-backed proposal storage, and deterministic exports (md/docx/pdf).
- Architecture: Containerized monolith with a separated React SPA frontend and Django API backend; PostgreSQL; optional Redis/Celery workers; deployed via Coolify which provides Traefik.
- Data: Relational core for identity/billing; proposal content in JSONB with GIN indexes; Row-Level Security (RLS) enforced via DB session variables.

## Repo layout (expected)
- api/ — Django project (accounts, orgs, proposals, billing, ai, exports, files)
- web/ — React SPA (SurveyJS-driven UX)
- docker-compose.yml — local dev stack (no proxy container)
- Dockerfile.api / Dockerfile.web — build images for Coolify
- scripts/, migrations/, etc.

## Technology stack
- Backend: Django + DRF, Postgres, Redis, Celery (async jobs for AI/exports)
- Frontend: React (Vite), SurveyJS
- AI: Provider abstraction (OpenAI GPT-5 / Google Gemini); optional RAG store of templates/exemplars
- Payments: Stripe subscriptions + customer portal + webhooks
- Exports: Markdown canonical → DOCX/PDF (pandoc/python-docx/weasyprint)
- OCR: ocrmypdf + pytesseract

## Deployment topology (Coolify + Traefik)
Pick one. You can switch later without code changes.

1) Single-application (recommended for MVP)
- Build SPA during CI and copy into API image under /static; serve with WhiteNoise.
- Traefik routes the root domain to the API container; API also serves /api endpoints.
- Pros: Simplest routing, no CORS/cookie complexity; 1 Coolify app.
- Cons: SPA rebuild required on API image deployment (mitigate with caching).

2) Dual applications (SPA + API)
- Two Coolify apps on the same domain: root → SPA; PathPrefix(`/api`) → API.
- Pros: Independent deploy cadence and scaling.
- Cons: Traefik path rules; CORS/session cookies to configure.

## Local development (Docker Compose)
- Services: db (Postgres), api (Django), web (React), redis, worker (Celery)
- No reverse proxy locally. API listens on 8000; web on 5173.
- Create .env files per service; see Env vars below.

## Environment variables (minimum)
Backend (API)
- DATABASE_URL=postgresql://user:pass@db:5432/granterstellar
- SECRET_KEY=...
- ALLOWED_HOSTS=*
- CORS_ALLOWED_ORIGINS=http://localhost:5173
- REDIS_URL=redis://redis:6379/0
- AI_PROVIDER=openai|gemini
- OPENAI_API_KEY=...
- GEMINI_API_KEY=...
- STRIPE_SECRET_KEY=...
- STRIPE_WEBHOOK_SECRET=...
- PUBLIC_BASE_URL=https://app.example.com
- EXPORT_ENGINE=pandoc|weasyprint
- OCR_ENABLED=true

Frontend (SPA)
- VITE_API_BASE=/api (single-app) OR https://app.example.com/api (dual-app)
- VITE_UMAMI_WEBSITE_ID=...
- VITE_UMAMI_SRC=https://umami.example.js (if self-hosted)

## Database notes
- Tables: users, organizations, org_users, proposals (content JSONB, schema_version), subscriptions, optional usage_events.
- Indexes: GIN on common JSONB paths used by filters.
- RLS: ON for all tables; API sets session vars (current_user_id, current_org_id, role) per request.

## Backend (Django) notes
- Apps: accounts, orgs, proposals, billing, ai, exports, files
- Middleware: Auth/JWT, RLS session setter, quota enforcement
- Endpoints (contract):
  - Planner: POST /api/ai/plan {grant_url|text_spec}
  - Writer: POST /api/ai/write {proposal_id, section_id, answers, file_refs[]}
  - Revisions: POST /api/ai/revise {proposal_id, section_id, change_request}
  - Exports: POST /api/exports {proposal_id, format} → job; GET /api/exports/{id}
  - Files: POST /api/files (PDF/images) → OCR pipeline

## AI providers
- Switch via env; log cost/latency per call.
- Prompts pass through a simple prompt-shield filter.
- RAG store with templates/exemplars improves determinism in Planner/Writer.

## Payments (Stripe)
- Subscription lifecycle via webhooks: checkout.session.completed, customer.subscription.updated, invoice.payment_failed.
- Downgrade cascade: when a user cancels, both their personal plan and organizations they admin downgrade at period end; admin transfer recomputes org tier immediately.
- Coupons/Promotions supported via Stripe.

## Exports
- Canonical: Proposal JSON → Markdown → DOCX/PDF
- Assets embedded and stable paths; idempotent output for same input.

## OCR & files
- PDFs/images processed via ocrmypdf/pytesseract; text extracted for AI.
- Virus scan hook (optional); file size/type validation enforced.

## Security
- Secrets only via env; no keys in repo.
- RLS enforces tenant isolation; least-privileged DB user.
- Traefik TLS via Let’s Encrypt; CSP/HSTS via Traefik middleware + Django settings.
- Rate limit sensitive endpoints (auth, AI writes, uploads).

## CI/CD
- Lint/typecheck (Python: ruff/mypy; JS: eslint/tsc)
- Unit/integration tests (RLS, quotas, webhooks, exports determinism)
- Build multi-stage Docker images for api/web

## Deploy on Coolify
Single-app (MVP)
1) Create Application → Dockerfile (API image that includes built SPA)
2) Domain: app.example.com; Traefik handled by Coolify
3) Internal port: 8000; Healthcheck: GET /healthz
4) Set Env vars (API + SPA vars)
5) Deploy; verify https://app.example.com/healthz

Dual-app
- API app: app.example.com/api path rule; internal port 8000
- SPA app: app.example.com root; internal port 80/5173 depending on server
- Ensure CORS/cookies configured for same-site path setup

## Backups & monitoring
- Backups: daily Postgres volume + uploads; test restore periodically
- Monitoring: health endpoints + logs; consider uptime checks

## Troubleshooting
- 4xx on /api: check CORS/ALLOWED_HOSTS and Traefik path
- Paywall not enforcing: check webhook delivery and subscription.status/current_period_end
- Export failures: ensure export engine installed and temp paths writable

---
This is a living document for the MVP. As services solidify, we’ll promote this to the main README and add exact commands and examples.
