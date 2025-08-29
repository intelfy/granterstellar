Granterstellar — Engineering Plan (cleaned 2025-08-29, updated end-of-day)

Note: Docs have been consolidated. See `docs/README.md` for the active docs index. This file remains as an engineering plan/status log.

Note: High-level plan and status. For authoritative architecture and setup, see `.github/copilot-instructions.md`, `README.md`, and `docs/install_guide.md`.

Legend: [x] done, [ ] todo, [~] in progress

## Current status (2025-08-29)
- Backend stable: Django API with JWT + Google OAuth, proposals, orgs, exports, billing/quotas.
- OAuth: Google, GitHub, and Facebook supported (prod-ready). Callbacks return structured JSON errors with `code`; cross‑provider account linking by email (case‑insensitive); invite acceptance honored when `state` carries an invite.
- Billing: seat-based caps, extras bundles (1/10/25), enterprise allocations; webhook handling solid in DEBUG.
    - Immediate cancel supported via POST /api/billing/cancel {"immediate": true} with org cascade.
    - Failed payment grace window honored for past_due via FAILED_PAYMENT_GRACE_DAYS (default 3). 
- AI: provider abstraction in place; composite provider routes GPT-5 (plan/write) and Gemini (revise/final format). New `/api/ai/format` endpoint added and wired in SPA to run only after all sections are approved.
    - Providers now include a deterministic file_refs context block in outputs (when provided); unit tests added.
    - Gating: In non-DEBUG, `/api/ai/write`, `/api/ai/revise`, and `/api/ai/format` require Pro/Enterprise. Free tier is blocked with HTTP 402 and header `X-Quota-Reason: ai_requires_pro`; DEBUG bypass allows local dev.
- Files: upload pipeline hardened. Hard file-size cap with HTTP 413 on overflow; MIME guess + magic‑signature checks (png/jpg/jpeg/pdf/docx); safe MEDIA_ROOT containment + no symlinks; optional virus‑scan hook with timeout; txt/docx/pdf extraction; optional image OCR via pytesseract behind `OCR_IMAGE=1`; optional PDF OCR via `ocrmypdf` behind `OCR_PDF=1`.
- SPA: auth + RequireOrg guards; deep-link persistence; assets under `/static/app/`; routes under `/app` (basename from `VITE_ROUTER_BASE`); dev refresh self-correct; NotFound route; minimal styling. Test-mode guard disables dev redirect; safeOpenExternal always opens in tests to satisfy spies.
- SPA OAuth: provider-specific callback dispatch (stored provider hint) and minimal error UX mapping backend `code` values; deep-link preserved across roundtrip.
- Billing UX: usage payload now includes `subscription.discount`; SPA usage banner surfaces active promo (percent/amount and duration) when present.
- Error pages: minimal Django templates for 400/403/404/500.
- Invites hygiene: expiry (`ORG_INVITE_TTL_DAYS`) and per‑org rate limiting (`ORG_INVITES_PER_HOUR`) implemented; acceptance logic prioritizes already_accepted over expiry; serializer fixed; tests cover create/list/revoke/accept/expiry/rate-limit.
- Docs: install guide rewritten (idiot‑proof), README expanded; env templates updated with FAILED_PAYMENT_GRACE_DAYS and inline purpose comments (APP_HOSTS, CSP_* including CSP_CONNECT_SRC). Added GitHub/Facebook OAuth keys and setup notes. New upload/backup settings documented: FILE_UPLOAD_MAX_BYTES, TEXT_EXTRACTION_MAX_BYTES, VIRUSSCAN_CMD, VIRUSSCAN_TIMEOUT_SECONDS; backups mount at `/backups`.
    - Added CSP_ALLOW_INLINE_STYLES escape hatch docs; default CSP now avoids 'unsafe-inline' in style-src.
    - Documented AI gating behavior and org scoping via `X-Org-ID`; async `{job_id}` responses and job polling notes.
    - Added RLS (Postgres) testing instructions and VS Code task reference (use DATABASE_URL + “API: test (RLS on Postgres)”).
- Tests: 25 core API tests passing (accounts, billing incl. seats/bundles/enterprise, exports determinism, invites). Additional files-upload security tests pass locally. SPA unit tests passing (RequireAuth/RequireOrg, OAuth callback deep-link, paywall upgrade CTA, authoring final-format visibility). Initial Postgres-only RLS tests added (skipped on SQLite).
    - Added AI gating unit tests (free blocked, pro allowed, DEBUG bypass) for write/revise/format.
    - RLS how-to documented in install guide; ready to run against a real Postgres via the VS Code task.
- OAuth tests: added Google (JWKS verify success/fail), GitHub edge cases (no verified emails → 400; prefer verified over unverified primary), Facebook edge case (no email → 400). Cross‑provider same‑email login maps to one account.
- Security hardening: landing `server.mjs` tightened (strict CSP, validated Umami src, Host not trusted, static GET/HEAD rate limiting). Uploads: safe path checks, MIME/signature validation, hard size caps with 413, optional virus-scan hook. SPA external navigation constrained via `safeOpenExternal` allow-list.
    - CSP tightened: no inline styles by default; `CSP_ALLOW_INLINE_STYLES=1` escape hatch available and documented.
- Lint/build: API ruff passes; web lint configured for JS/JSX (flat config) and passes; TypeScript lint intentionally deferred. Vite build ok.
    - Dev tasks: VS Code tasks consolidated; added Postgres-only RLS test task entry.

## Exit criteria (early testers)
- Single-app deployment via Coolify/Traefik; Postgres + JSONB + RLS; quotas enforced (free/pro/enterprise).
- AI-assisted authoring loop stubs; deterministic exports (md/pdf/docx).
- Basic org/user management with invites and admin transfer.

0) Landing and Marketing [x]
- [x] Simple landing page
- [x] Email signup for waitlist
- [x] Mailgun API to add emails
- [x] Add Umami analytics to landing + SPA (self-hosted or cloud)
    - [x] Environment config for UMAMI_WEBSITE_ID and endpoint
    - [x] Analytics host configured (https://data.intelfy.dk/script.js)
    - [x] Cookie banner/update privacy page if required
    Why: Track funnels and feature adoption; align with privacy policy.
        Interacts with: SPA router, Traefik middlewares/headers (via Coolify), privacy.html.
    Security: Disable PII collection; respect Do Not Track.
    Notes (security): `server.mjs` validates `VITE_UMAMI_SRC` (must be https and end with /script.js), derives CSP allow-lists from that origin, avoids trusting Host header, and rate-limits static GET/HEAD.

1) Platform Foundations (DevOps + Project skeleton)
- [x] Repository housekeeping
    - [x] .editorconfig, .gitignore, SECURITY.md (baseline)
    - [x] Pre-commit hooks (ruff for Python; eslint for JS); prettier/black/isort can be added later
- [x] Environment and secrets
    - [x] .env.example for all services (no secrets committed)
    - [x] Local .env files and docker-compose overrides
        - [x] Added `docker-compose.override.sample.yml` for local ports/DEBUG
        - [x] Create `.env` locally from `.env.example` as needed (developer-specific)
        - [x] Added `FAILED_PAYMENT_GRACE_DAYS` to env templates; inline comments for APP_HOSTS and CSP_* (incl. CSP_CONNECT_SRC) to clarify purpose
- [~] Docker Compose stack
    - [x] Services: api (Django), web (React SPA), db (Postgres), cache (Redis), worker (Celery), optional: kroki (diagrams)
        - Note: In Coolify, Traefik is provided by the platform; no proxy container in our compose.
    - [x] Healthchecks and depends_on for startup order
    - [x] Volumes for db data and uploaded files
    - [x] CI pipeline (GitHub Actions)
    - [x] Lint + unit tests for API and SPA
        - [x] API: Django test runner wired with a health check test
        - [x] SPA: ESLint job added (flat config v9). Note: lint script targets JS/JSX only to avoid TS parser setup; TS lint can be enabled later with @typescript-eslint.
    - [x] Frontend unit tests: guards + deep-link persistence + paywall upgrade CTA basics
    - [x] Build container images
    Why: Reproducible environments and fast feedback loops reduce risk.
    Interacts with: All services; ensures consistent env var names across API/SPA/Proxy.
    Contract: docker compose up should start all services healthy; CI must pass before merge.
    Security: Secrets only via env; no tokens in repo; pinned base images.

2) Database (PostgreSQL)
- [x] Bootstrap Postgres (UTF-8, UTC) — via compose/env conventions
- [x] Schema/models: Users, Organizations, OrgUsers, Proposals (JSONB), Subscriptions (seats), ExtraCredits
    - [x] JSONB GIN indexes on common paths (content, shared_with)
    - [ ] Optional: UsageEvents (for AI metering)
- [x] Session context helpers (GUCs) and middleware to set user/org/role
- [~] RLS policies: orgs, proposals, subscriptions enforced; expand tests
    - Done: Added matrix tests for insert/update/share visibility and admin-only writes (skip on SQLite).
- [x] Migrations + dev seed (`manage.py seed_demo`)
- [~] DB tests: smoke coverage; initial RLS tests added (Postgres-only; skipped on SQLite). Expand coverage later.
    - Done: Postgres-only tests in `db_policies/tests/test_rls_policies.py` (matrix expansions planned).

    Data notes
    - Org tier derives from the admin’s plan; transfer recomputes immediately.
    - Proposal JSONB is the source of truth; keep migration-upgradable via schema_version.

3) Backend API (Django)
- [x] Project scaffolding
    - [x] Django project + apps: accounts, orgs, proposals, billing, ai, exports, files
    - [x] Settings for Postgres (via dj-database-url), CORS/CSRF, static/media
- [~] AuthN/AuthZ
    - [x] JWT issuance: POST /api/token, /api/token/refresh
    - [x] OAuth (Google, GitHub, Facebook):
        - Google: /api/oauth/google/start, /api/oauth/google/callback (JWTs; DEBUG email shortcut; JWKS signature verified in prod)
        - GitHub: /api/oauth/github/start, /api/oauth/github/callback (reads verified emails; differentiates `email_unverified` vs `email_not_found`; DEBUG email shortcut)
        - Facebook: /api/oauth/facebook/start, /api/oauth/facebook/callback (requires email; returns `email_not_found` when absent; DEBUG email shortcut)
        - All callbacks return structured JSON errors `{ ok, error, code }`, accept `state` invite tokens, and link accounts across providers by email (case‑insensitive)
    - [x] DB session vars middleware for RLS (accounts.middleware.RLSSessionMiddleware)
    - [~] Expand RLS role test coverage (initial Postgres-only tests in `db_policies/tests/test_rls_policies.py`)
- [~] Core endpoints
    - [x] Users: GET /api/me
    - [ ] Profile update
    - [x] Organizations: CRUD, invite, transfer ownership, list members
    - [x] Org membership: add/remove/change roles (admin only)
    - [x] Proposals: CRUD with scoped queryset; quota enforced on create
    - [~] Proposal autosave (PATCH) and versioning metadata
        - [x] PATCH autosave implemented and covered by tests
        - [ ] Versioning metadata pending
    - [x] Exports: POST /api/exports (md|pdf|docx), GET /api/exports/{id}; Markdown → PDF (ReportLab) / DOCX (python-docx)
    - [x] Files: POST /api/files (pdf/png/jpg/jpeg/docx/txt) with txt/docx/pdf extraction + optional OCR
        - [x] Path traversal guards: all file helpers verify paths under MEDIA_ROOT (no symlinks)
        - [x] MIME guess + magic-signature validation for png/jpg/jpeg/pdf/docx
        - [x] Hard size cap with HTTP 413 `file_too_large`
        - [x] Optional virus-scan hook with timeout; fail-closed on errors
- [x] AI orchestration endpoints
    - [x] Planner: POST /api/ai/plan
    - [x] Writer: POST /api/ai/write
    - [x] Revisions: POST /api/ai/revise
    - [x] Long-running tasks via Celery; job status endpoints
        - [x] Exports run async behind feature flag (EXPORTS_ASYNC) with polling via GET /api/exports/{id}
        - [x] AI endpoints offload behind `AI_ASYNC=1` (with Redis). POST returns `{job_id}`; poll `GET /api/ai/jobs/{id}`.
    - [x] Final formatting endpoint `/api/ai/format` implemented and tested; SPA button triggers it only after all sections approved
- [~] Billing/Quotas
    - [x] Stripe customer + subscription sync (webhook upsert implemented) and checkout initializer
        - Checkout endpoint added with DEBUG fallback; SPA wired to open returned URL
    - [x] Webhook handlers implemented; DEBUG accepts unsigned; prod verifies with STRIPE_WEBHOOK_SECRET
    - [x] Quota enforcement middleware (free=1 active personal; pro monthly); DRF permission CanCreateProposal
    - [x] Customer portal link endpoint
    - [x] Cancel/Resume endpoints: POST /api/billing/cancel, /api/billing/resume (user and org admin scope)
    - [x] Immediate cancel: POST /api/billing/cancel {"immediate": true} cancels now and cascades org mirrors
    - [x] Usage payload includes subscription.cancel_at_period_end and current_period_end
    - [x] Pro monthly cap scales with seats: effective_cap = seats * QUOTA_PRO_PER_SEAT + extras (ExtraCredits)
    - [x] Extras bundles (1/10/25) credited via invoice webhook when PRICE_BUNDLE_* set
    - [~] Coupons/Promo codes: validate and apply via Stripe
        - [x] Accept coupon/promo code in checkout; apply Promotion Code or Coupon when Stripe is configured
        - [x] Persist discount info and surface in usage (API stores on Subscription.discount; SPA shows "Promo" in usage banner)
        - [ ] End-to-end live-mode verification of promotions in staging/production
     - [~] Downgrade cascades:
         - [x] Enforcement after current_period_end covered by test `billing.tests.test_enforce_cascade.EnforceCascadeTests`.
         - [x] Immediate-cancel case supported and covered by tests.
         - [x] Failed payment grace window respected (setting: FAILED_PAYMENT_GRACE_DAYS).
      - [x] Admin transfer effects:
          - When org admin is changed, recompute org tier from new admin's plan and re-enforce quotas immediately.
      - [x] Safety-net enforcement:
          - Daily job to enforce cancel_at_period_end after current_period_end (management command + compose beat)
    - [x] Quota check logic for AI writes (personal vs org-admin plan) with DEBUG bypass and org scope via `X-Org-ID`; unit tests cover allow/block paths.
- [~] Files/OCR
    - [~] Basic image OCR via pytesseract/PIL behind flag `OCR_IMAGE=1` (see `files/views.py`).
    - [x] PDF text extraction via pdfminer.six; optional OCR pipeline behind `OCR_PDF=1` using `ocrmypdf` CLI when available.
    - [x] Content-length cap (FILE_UPLOAD_MAX_BYTES) returns 413; extraction capped (TEXT_EXTRACTION_MAX_BYTES); virus-scan hook with timeout.
- [ ] Prompt shield
    - [ ] Central prompts + basic injection screening (e.g., Rebuff/Promptfoo integration or rules)
    - [~] Tests
    - [x] Per-app Django tests green (accounts, billing, exports)
    - [x] Quota, usage, webhook behavior (DEBUG) covered
    - [x] Auth flows (OAuth callback deep-link unit test in SPA)
    - [~] RLS policy behaviors (initial Postgres-only tests; expand matrix: creator vs org-admin vs member vs anon)
    - [x] Export determinism (md/pdf/docx checksum) tests
     - [~] Subscription lifecycle tests:
         - [x] Cancel/Resume endpoints toggle cancel_at_period_end
         - [x] Webhook customer.subscription.deleted marks status=canceled and sets canceled_at
         - [x] Downgrade after current_period_end enforces free tier for user and their orgs
         - [x] Admin transfer recomputes org tier immediately
         - [ ] Coupon applied → tier/limits reflect promotion during validity window
         - [x] Immediate cancel and past_due grace window behavior
    Why: API is the single source of truth; enforces security and business rules.
    Interacts with: DB RLS (via session middleware), Stripe, AI providers, SPA SurveyJS.
    Contract examples:
        - Planner: input {grant_url|text_spec}; output {sections:[{id,title,inputs[]}], schema_version}
        - Writer: input {proposal_id, section_id, answers, file_refs[]}; output {draft_text, assets[], tokens_used}
        - Revisions: input {proposal_id, section_id, change_request}; output {draft_text, diff}
    Security: JWT + role checks; idempotent webhooks; rate limiting on AI endpoints; file type/size validation.

4) AI Providers and Abstractions
- [x] Provider abstraction (local stub in `api/ai/provider.py`; switchable via env for real providers later)
 - [x] Cost/latency logging per request (AIMetric model + instrumentation in views/tasks; migration 0002)
- [ ] Safety filters (max tokens, rate limiting per plan)
- [ ] Deterministic sampling settings for exports where possible
 - [ ] RAG store (templates + exemplars) to guide Planner/Writer prompts and Formatter styling
     - [ ] Curate sample proposals and section templates (self-hosted data only)
     Why: Hybrid model minimizes cost while keeping quality; RAG stabilizes structure/voice.
    Interacts with: ai.* endpoints, quota middleware, exports (for deterministic render).
     Contract: Provider interface generate(prompt, opts) returns {text, usage, model_id}.
     Security: PII redaction rules in prompts where feasible; audit logs of prompts/responses.
- [ ] Prepare batch task for Gemini-2.5-Flash to twice a week search web for templates and successful/winning proposal samples for common grant calls we don't currently have templates for and integrate them into the RAG. Files should be categorized as either samples or templates. Log all new files added.
- [ ] Implement AI/user interaction flow: The user provides the open call they're applying for --> The planner (using web search to review the user's input URL for the open call and compares against templates/samples in the RAG) determines what sections will be needed and what information should be prefilled (drawing also from the organization metadata like name/description) and what questions to ask the user per section --> The writer parses the user's answers per section and fleshes out the section for review/revision until user approves --> the user is asked the next set of questions for the next section --> the writer repeats --> ... --> once all pre-planned sections are done, the user approves the text a final time, before the formatter structures it (prioritizing a good looking PDF formatting) according to a template (if one exists) or inference and similar sample writing and web search grounding (if a template does not exist) --> Formatter presents a mockup of the final .PDF versio of the file, formatted to closely resemble the templates/samples in layout --> The user exports the formatted file in their chosen extension, (or opens the editor and is asked which section they would like to edit, and whether they would like to edit the raw text manually or rerun the AI interactions for that section)
- [ ] Implement AI memory per user (user uploads persisted in "My files" unless deleted, commonly given user answers persisted in database and suggested on sections - such as the user giving a budget in one proposal and it being suggested automatically when writing the next - etc.)

5) Export Pipeline (Deterministic)
- [x] Canonical renderer: Proposal JSON → Markdown
- [x] Markdown → DOCX (python-docx) and → PDF (ReportLab)
- [ ] Asset embedding (images/diagrams) and stable paths
- [x] Idempotency via normalized checksums (same input → same checksum)
    Why: Single canonical Markdown avoids divergence across formats.
    Interacts with: proposals.content JSONB, files storage, AI diagram outputs.
    Contract: POST /exports creates job {id,status,url_when_ready}; outputs stored with content hash.
    Security: Validate access before generating/downloading; clean temp files.

6) Frontend (React SPA)
    - [x] Scaffold SPA (Vite)
    - [x] Auth flow (JWT for DEBUG; Google/GitHub/Facebook OAuth; logout)
        - [x] RequireAuth guard; deep-link `next` across login/OAuth/RequireOrg/register
        - [x] OAuth callback surfaces backend error reasons on Login (maps codes like `email_unverified`, `email_not_found`, `token_exchange_failed`)
    - [x] Dashboard basics
        - [x] My proposals list + create
        - [x] Organizations list/management + invites; admin transfer
        - [ ] Profile edit (email, name)
    - [~] Authoring flow
    - [x] Show AI draft vs previous content; Approve/Revise; autosave JSONB (PATCH)
    - [x] Final formatting step added (deferred until all sections approved)
        - [x] Unit tests: final-format appears only when all sections approved; triggers /api/ai/format and renders preview
    - [x] AI async offload: plan/write/revise/format feature-flagged behind AI_ASYNC with Celery jobs and polling
    - [ ] Integrate SurveyJS
    - [x] File uploads per section; OCR display in authoring UI (with preview)
    - [x] Exports UI (md/docx/pdf) with polling
    - [x] Paywall/upgrade
        - [x] Enforce caps; Upgrade opens checkout; portal/cancel/resume controls
    - [x] Routing/base path & 404s
        - [x] BrowserRouter basename from `VITE_ROUTER_BASE` (default `/app`); assets served from `/static/app/`; dev refresh self-correct on deep links
        - [x] NotFound page + catch-all; `/404` convenience path
        - [x] Tests account for jsdom limitations: dev redirect disabled during tests
    - [x] Styling policy
        - [x] Minimal markup only; no inline styles; error pages plain HTML (see `docs/design_system.md`)
    - [ ] Analytics/tests
        - [x] Umami integration
    - [~] SPA tests
            - [x] Unit: RequireAuth, RequireOrg, OAuth callback deep-link, paywall upgrade CTA
            - [ ] E2E: deep-link across OAuth + register; paywall end-to-end
    - [ ] Extract all user-facing text and copy from the entire #codebase into a standalone keys file, so text on the app can be easily edited in a single location. Annotate and organize the keys by section so it is clear exactly when and how the user will encounter them. Make sure keys are escaped when fetched, so I do not have to manually escape symbols in the keys file. Prepares for front-end styling and i18n. 
        - [ ] On-page copy
        - [ ] Error messages, blurbs, labels
        - [ ] Notifications & Banners
        - [ ] E-mail bodies and subjects
        - [ ] Per-page SEO metadata (titles, meta descriptions, keywords, etc)
        - [ ] Static survey text
7) Proxy and Networking (Coolify + Traefik)
- [~] Use Coolify-managed Traefik as reverse proxy (TLS via Let's Encrypt)
- [ ] Routes: domain root → landing (`/`), SPA at `/app` (deep links supported), API at `/api`, assets at `/static/app/`, and uploads at `/media/` served by API container
- [ ] Define Traefik labels (if needed) or configure via Coolify UI
- [ ] CORS and security headers (CSP, HSTS in prod): set via Traefik middlewares and API settings
    Why: Coolify standardizes deployment with Traefik handling routing and certificates.
    Interacts with: SPA asset hosting, API, file uploads, analytics endpoint.
    Security: Strict CSP with allowlists; gzip/brotli; large body limits for uploads only; HTTPS enforced by Traefik; landing server listens HTTP-only behind proxy.
    Deployment note: For MVP, prefer single-app topology (SPA built into API image) to avoid cross-origin and complex router rules; move to separate SPA/API apps later if scaling requires.

8) Operations and Security
- [x] Secrets management (env vars documented; no keys in repo)
- [x] Backups (Postgres DB)
    - [x] Daily `pg_dump` script writes gzipped SQL to `/backups` (mounted volume)
    - [x] Compose wiring for `/backups` volume; optional dedicated backup service
    - [x] Docs: install guide updated; notes for Duplicati integration
    - [ ] Uploads backup (media) strategy documented and verified
- [ ] Basic monitoring/logging (structured logs; health endpoints)
- [ ] Security baseline
    - [~] Dependency scan (pip/npm)
        - Triaged SAST/dep alerts; hardened landing server CSP/Host/rate-limit, upload path checks, SPA external nav allow-list. Re-run scan after deploy.
    - [ ] Auth brute-force rate limiting
    - [ ] Data retention/privacy review; update privacy page
    - [ ] RLS review and least-privileged DB user
    Why: Early testers still need resilience and data safety.
    Interacts with: CI/CD, DB, file store, privacy/legal docs.
    Contract: Daily backups verified restore; health endpoints used by uptime monitors.

9) Billing (Stripe) — Acceptance Tests
- [ ] New signup → checkout → active subscription reflected in app
- [~] Downgrade/cancel → plan changes at period end
- [ ] Free → paywall reached → upgrade CTA works
 - [x] Pro seat scaling: quantity change → webhook updates seats → /api/usage reflects seats * QUOTA_PRO_PER_SEAT (covered by tests)
 - [x] Extras bundle crediting: invoice with PRICE_BUNDLE_* → /api/usage includes extras (covered by tests)
- [ ] Webhooks verified and recover on retries
 - [ ] Admin cancels → org downgraded at period end (no perpetual tier carryover)
 - [x] Admin transfer recomputes org tier instantly
    Why: Confident subscription lifecycle handling incl. proration and failures.
    Interacts with: Quota middleware, UI paywall, Subscriptions table, email notices (optional).
    Contract: Webhook processing is idempotent; status in DB matches Stripe.

10) Front End Design (DEFER UNTIL BACK-END COMPLETE)
- [ ] Paginate app into separate views with a sidebar navigation
    - [ ] Account
        - Set/Edit name
        - Set/edit contact email (if separate from Oauth email)
        - Set avatar image
        - Add title & bio
        - Connect more Oauths
        - Delete account (all proposals written by account get tied to Org ID instead) (DANGER ZONE, confirm by re-authenticating with Oauth)
            - Billing --> Redirect to billing view
    - [ ] Organizations
        - See list of organizations you are admin/member of in table with names, logos, description, allocated monthly proposals, current usage
        - Create new organization
        - Edit existing organizations
            - Add/edit name and description
            - Set logo image
            - Change allocations (ENTERPRISE ADMIN ONLY, PRO USERS DEFAULT 100% ALLOCATION OF PROPOSALS TO THE ONE ALLOWED ORG ADMINSHIP)
            - Invite/edit/remove members
            - Delete organization (DANGER ZONE, confirm by inputting organization name in text field) (proposals written by members of organization get tied to users and no longer accessible to ex-org admin)
    - [ ] Proposals
        - See list of proposals, their status, times exported.
        - Create proposals --> Opens new full-screen editor view with survey on the left hand-side of the screen, drafting (by AI) happening dynamically on the right-hand side of the screen, so users can watch the document expand in real-time. Streaming responses (if enabled)
        - Edit proposals --> Determine whether to manually edit or rerun AI-assisted writing
                --> If manual, open complete file in md-compatible text editor
                --> If rerunning assisted writing, let user choose specific section or "from the top" and rerun AI assisted survey logic on selected sections
        - Archive proposals
        - Delete proposals (instantly deletes, unlike archive which stores for 6 weeks)
        - Share proposals (enter e-mail address of user you are sharing with or select from drop-down of members of organization)
        - See proposals shared with you (including who created them)
        - See/edit/archive/delete all proposals within org (ADMINS ONLY) including who created them
        - Export proposals (select supported format)
    - [ ] Archive
        - See archived proposals
        - Restore or delete archived proposals
    - [ ] My files
        - See all uploaded files and how many times they have been used within proposals
        - Edit, overwrite or delete uploaded files
        - Download files
    - [ ] Logs (ORG AND ENTERPRISE ADMINS ONLY)
        - See all logs of organization(s). Creations, archivings, deletions, etc. and which user did what and when
    - [ ] Settings (UI settings like dark/light theme, more to come)
    - [ ] Billing (billing portal. Upgrade/downgrade/cancel/buy top-up bundles, see billing dates, see last payment, see last invoice, etc)
    - [ ] Login
    - [ ] Register
    - [ ] Logout confirmation
    - [ ] Billing confirmation
    - [ ] Dashboard (shared organization notes, usage statistics, quick overview over latest proposals, charts showing helpful information), space for marketing and update logs from Granterstellar.
    - [ ] Deletion confirmations
    - [ ] Get support page with live chat and ability to submit tickets
    - [ ] Custom templates (allow users to upload their own grant proposal templates for the AI to fetch)
    - [ ] Style modals, error popups, other dynamic content
    - [ ] Review and update copy across app, pages, errors, banners, modals, etc, to be more user-friendly and less technical.
- [ ] Style pages one by one with iterations and approval for each page before moving on. Prefer global variables and light-weight CSS when able. Take inspiration from landing page for general design language. Should be modern, sleek, lots of full-page pages with plenty of white-space, easing transitions between pages, survey questions, etc.. Make use of templates folder. Design language should remind users of communicating with a living typewriter.


11) Release Readiness (Early Testers)
- [ ] Smoke test checklist (install, signup, create org, author one proposal, export all formats)
- [ ] Seed demo content (optional)
- [ ] Onboarding doc for testers + feedback channel
- [ ] Changelog for MVP
- [ ] Deploy to test environment (compose) and capture runbook
 - [x] README updated for full app: overview, architecture, local dev, env vars, Coolify/Traefik deployment, CI, backups, security/RLS, Stripe/webhooks, AI limits, troubleshooting
     - [x] Docs index at `docs/README.md` with links to detailed guides
     - [x] OAuth callback, Stripe portal, exports determinism, base path, error pages, styling policy captured
    Why: Ensure a predictable first-run experience for testers.
    Interacts with: All systems; runbook helps ops and support.

Deferred/Post-MVP (tracked but not required for early testers)
- [ ] Forum/community features
- [ ] Enterprise SSO (SAML/OIDC)
- [ ] Advanced diagram rendering via dedicated Kroki service
- [ ] Granular export theming/branding
- [ ] Multi-tenant backups/restore UI

Notes
- Proposal JSON schema should be versioned; migrations must preserve backward compatibility.
- Prefer async jobs for AI generation and exports; keep request latency predictable.
- Keep Markdown as the canonical export; other formats derive from it to avoid divergence.

12) Superadmin Dashboard
- [ ] Build a superadmin-only dashboard (separate from org admin) to manage global operations
    - [ ] Org quota overrides (enterprise/custom)
        - Set per-organization overrides for `active_cap` and/or `monthly_cap` (stored in DB; enforced by quota checker)
        - View current Stripe-linked tier/status and effective limits
    - [ ] Coupons/Promotions
        - Option A: Link out to Stripe to create/manage Coupons/Promotion Codes (preferred, source of truth)
        - Option B (later): Minimal UI to create Stripe coupons via API and list active promotions
        - Allow attaching a promo to a checkout link or customer for troubleshooting
    - [ ] Switch AI models per function (planner, writer, formatter) to other OpenAI-compatible providers such as OpenRouter or Claude. Require API keys to be set in ENV_VAR. Add option to enable/disable streaming per model.
    - [ ] User restrictions
        - Ban/suspend user (login disabled, sessions revoked)
        - Apply rate limits/restrictions (e.g., AI writes disabled) for policy or abuse cases
    - [ ] Housekeeping tools
        - Retry failed Stripe webhooks; force re-sync a customer/subscription
        - Export monthly usage summaries (CSV/JSON)
        - Clear caches; trigger background jobs (rebuild indexes, backfills)
        - Toggle feature flags (if/when added)
    - [ ] Audit & access control
        - Record all superadmin actions (who/when/what) with immutable audit logs
        - Require superuser role + optional second factor; rate limit and IP-allowlist access
    - [ ] Analytics (with diagrams)
        - Users/orgs/enterprises total
        - Highest token-spending users and orgs
        - Most editing users and orgs
        - Bundle purchases
        - Users/orgs consistently approaching usage allocation (so we can upsell)
        - Computed averages of token spends, proposal edits, etc globally.
    Why: Centralized ops control for support, enterprise SLAs, and incident response.
    Interacts with: Quota middleware/service, Stripe API/webhooks, auth/session store, background workers.
    Contract: Minimal admin REST endpoints under `/api/admin/*` (IsSuperUser) and/or Django Admin custom pages.
    Security: Principle of least privilege; audit every action; avoid storing Stripe secrets in UI—use server-side API.
    - [ ] Lightly style superadmin dashboard for visual clarity.

## Done to date (highlights)
- Accounts, orgs, proposals, billing, ai, exports, files apps; per-app tests green.
- OAuth (Google, GitHub, Facebook) + JWT; cross‑provider email linking; structured callback errors; Login surfaces provider error reasons; DEBUG password/OAuth shortcuts in dev.
- Proposals: scoped queryset; quota permission on create; autosave PATCH.
- Billing: seats mirrored; extras bundles via invoice; checkout/portal/cancel/resume; admin transfer recompute.
- Exports: markdown canonical; deterministic PDF/DOCX; optional async (Celery) with polling.
- SPA: proposals list/create; org management + invites; exports UI; upgrade + portal; RequireAuth/RequireOrg; base path alignment; NotFound; minimal styling.
- SPA tests green (unit); jsdom navigation quirks handled via test guards; Vite prod build clean (no source maps/console).
- Docs: README updated with expanded env keys; exports_async.md; design_system.md; install guide rewritten with env reference (APP_HOSTS, CSP_CONNECT_SRC), copy-paste env block, and Coolify runbook.
- Backups: daily pg_dump to `/backups` with compose volume; docs updated.
- Uploads: hard size caps with 413; MIME/magic validation; safe MEDIA_ROOT-only access; optional virus-scan hook with timeout; files security tests added.

## Next up (short-term)
- Stripe lifecycle: live-mode verification of coupons/promo codes; ensure usage reflects active discounts end-to-end in staging.
- Invites: SPA polish for invite acceptance UX (backend hygiene done with expiry/rate-limit).
- RLS coverage: expand Postgres tests; document least-privileged DB user; consider migration hardening for policies.
- SPA tests: export-after-formatting flow; end-to-end deep-link across OAuth + register; paywall E2E.
- Operations: verify DB restore procedure; add uploads (media) backup guidance; minimal monitoring/healthcheck runbook; dependency scans re-run.
- Proxy/CSP: finalize Traefik routes and tighten CSP allow-lists per environment (include analytics host only where needed).
- Linting: If/when needed, add @typescript-eslint (v8) to enable TS lint; adjust flat config accordingly.
 - RLS: Run Postgres-only RLS test task with a real DATABASE_URL; expand matrix (creator/admin/member/anon). Steps documented in `docs/install_guide.md`.
 - AI: Optional async-mode tests for AI endpoints (job polling) when `AI_ASYNC=1` is enabled.