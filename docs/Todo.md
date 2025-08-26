Granterstellar — Early Testers Release Plan

Legend: [x] done, [ ] todo, [~] in progress

Exit criteria for this milestone: A self-hostable Docker Compose stack with a working React SPA + Django API deployed via Coolify behind Traefik, Postgres (with JSONB + RLS), Stripe-enforced quotas, AI-assisted proposal authoring loop, deterministic exports (md/docx/pdf), and basic org/user management ready for early testers.

0) Landing and Marketing [partially done]
- [x] Simple landing page
- [x] Email signup for waitlist
- [x] Mailgun API to add emails
- [ ] Add Umami analytics to landing + SPA (self-hosted or cloud)
    - [ ] Environment config for UMAMI_WEBSITE_ID and endpoint
    - [ ] Cookie banner/update privacy page if required
    Why: Track funnels and feature adoption; align with privacy policy.
        Interacts with: SPA router, Traefik middlewares/headers (via Coolify), privacy.html.
    Security: Disable PII collection; respect Do Not Track.

1) Platform Foundations (DevOps + Project skeleton)
- [ ] Repository housekeeping
    - [ ] .editorconfig, .gitignore, CODEOWNERS (optional), SECURITY.md (baseline)
    - [ ] Pre-commit hooks (black, ruff, isort for Python; eslint, prettier for JS)
- [ ] Environment and secrets
    - [ ] .env.example for all services (no secrets committed)
    - [ ] Local .env files and docker-compose overrides
- [ ] Docker Compose stack
        - [ ] Services: api (Django), web (React SPA), db (Postgres), cache (Redis), worker (Celery), optional: kroki (diagrams)
        - Note: In Coolify, Traefik is provided by the platform; no proxy container in our compose.
    - [ ] Healthchecks and depends_on for startup order
    - [ ] Volumes for db data and uploaded files
- [ ] CI pipeline (GitHub Actions)
    - [ ] Lint + type-check + unit tests for API and SPA
    - [ ] Build container images
    Why: Reproducible environments and fast feedback loops reduce risk.
    Interacts with: All services; ensures consistent env var names across API/SPA/Proxy.
    Contract: docker compose up should start all services healthy; CI must pass before merge.
    Security: Secrets only via env; no tokens in repo; pinned base images.

2) Database (PostgreSQL)
- [ ] Bootstrap Postgres (UTF-8, timezone UTC)
- [ ] Schema and models (align with specs; JSONB for proposal content)
    - [ ] Users (id, email, username, roles, subscription_tier, payment_frequency, billing_period_ends, last_payment)
    - [ ] Organizations (id, name, admin_id, description, files_meta, created_at)
    - [ ] OrgUsers (org_id, user_id, role)
    - [ ] Proposals (id, user_id, org_id, shared_with[], state, last_edited, downloads, content JSONB, schema_version)
    - [ ] Subscriptions (id, user_id|org_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end)
    - [ ] JSONB GIN indexes on common filter paths (e.g., content->'meta', content->'sections')
    - [ ] Optional: UsageEvents (id, user_id, org_id, proposal_id, section_id, type:WRITER_COMPLETION, tokens_used, created_at)
- [ ] Session context helpers
    - [ ] Postgres functions to set current_user_id, current_org_id, role
- [ ] RLS policies (secure by default)
    - [ ] Users: self-read; admin-only writes
    - [ ] Organizations: admin access; members read
    - [ ] Proposals: creator OR shared_with OR org-admins can read; creator and org-admins can write
    - [ ] Subscriptions: owner/admin read/write
- [ ] Migrations + seed dev data
- [ ] DB tests
    - [ ] RLS policy tests for all roles
    - [ ] Index usage on typical queries
    Why: Hybrid relational + JSONB supports rigid identity/billing with flexible proposal schemas.
    Interacts with: API ORM models, quota logic, export renderer, search filters.
    Contract: API sets session vars per request so RLS enforces tenant isolation without app-side filtering.
    Security: RLS ON for all tables; least-privileged DB role for API; parameterized queries only.

    Data sources and interactions per table (authoritative flows)
    - Users
        - Fed from: OAuth profile on signup; profile updates via /users/me; Stripe customer linkage stored after checkout success.
        - subscription_tier/payment fields mirror Stripe objects for convenience; Stripe is source of truth.
        - billing_period_ends and last_payment set by webhooks: customer.subscription.updated and invoice.payment_succeeded.
    - Organizations
        - Fed from: /orgs CRUD; admin_id set on create or transfer via /orgs/transfer.
        - subscription tier is derived from admin user's subscription_tier; do not edit directly; kept in sync by webhook handlers and admin transfer logic.
        - files_meta summarizes uploaded assets (count/size/ids) from /files service.
    - OrgUsers
        - Fed from: invites/acceptance and role management endpoints; used by RLS to authorize members.
    - Proposals
        - Fed from: SurveyJS SPA state and AI Writer outputs; autosave PATCH updates content JSONB and last_edited.
        - shared_with[] managed by share/unshare endpoints; downloads incremented by exports service upon successful file generation.
        - schema_version tracks renderer compatibility; migration scripts must up-convert older drafts.
    - Subscriptions
        - Fed from: Stripe API (checkout, billing portal) via webhooks; created/updated rows reflect stripe_customer_id, stripe_subscription_id, tier, status, current_period_end.
        - Interacts closely with: Users (personal plan), Organizations (derived org tier from admin user's plan), Quota middleware.
        - Cancellation/downgrade rule: when a user cancels, both their personal access and any Organizations they admin must downgrade at the end of the current billing period (no grace bypass). Implement as a scheduled effect driven by current_period_end from Stripe.
        - On admin transfer, recompute org tier based on new admin user's plan immediately.
    - UsageEvents (optional but recommended)
        - Fed from: each successful Writer completion; used to compute per-month usage vs plan limits for auditing and support.

3) Backend API (Django)
- [ ] Project scaffolding
    - [ ] Django project + apps: accounts, orgs, proposals, billing, ai, exports, files
    - [ ] Settings for Postgres, Redis, CORS, media/static, logging
- [ ] AuthN/AuthZ
    - [ ] OAuth (e.g., Google) sign-in + JWT issuance
    - [ ] API key/session middleware to set DB session vars for RLS
    - [ ] Roles: admin, user, guest (enforced in views and RLS)
- [ ] Core endpoints
    - [ ] Users: me, profile update
    - [ ] Organizations: CRUD, invite, transfer ownership, list members
    - [ ] Org membership: add/remove/change roles (admin only)
    - [ ] Proposals: CRUD, share/unshare, list by org/user
    - [ ] Proposal autosave (PATCH) and versioning metadata
    - [ ] Exports: create job and download URLs (md/docx/pdf)
    - [ ] Files: upload (PDF/images), list, delete
- [ ] AI orchestration endpoints
    - [ ] Planner: given grant link/specs → section plan JSON
    - [ ] Writer: given section inputs/files → draft section text (+ optional diagrams)
    - [ ] Revisions: apply user change requests and produce new diff
    - [ ] Long-running tasks via Celery; job status endpoints
- [ ] Billing/Quotas
    - [ ] Stripe customer + subscription sync
    - [ ] Webhooks: checkout.session.completed, customer.subscription.updated, invoice.payment_failed
    - [ ] Quota enforcement middleware (free = 1 proposal completion; paid = monthly quota)
    - [ ] Customer portal link endpoint
    - [ ] Coupons/Promo codes: validate and apply via Stripe promotions/coupons
     - [ ] Downgrade cascades:
         - On cancellation (status = canceled at_period_end): mark user pending_downgrade and store current_period_end. On or after that time, set user.subscription_tier = free; for each org where user is admin_id, set derived tier to free as well.
         - On immediate cancellation (if configured): apply changes at once.
         - On failed payment: set grace period per Stripe status; enforce paywall if past grace.
     - [ ] Admin transfer effects:
         - When org admin is changed, recompute org tier from new admin's plan and re-enforce quotas immediately.
     - [ ] Quota check logic:
         - For Writer endpoint, determine context: if proposal.org_id present, evaluate quotas against that org's admin user plan; else use the author's personal plan.
         - Deny with paywall when exceeding plan; optionally allow purchase of overage bundles.
- [ ] Files/OCR
    - [ ] OCR pipeline (ocrmypdf/pytesseract) for PDFs/images; text extraction service
    - [ ] Content-length/timeouts; virus scan hook (optional, stub ok)
- [ ] Prompt shield
    - [ ] Central prompts + basic injection screening (e.g., Rebuff/Promptfoo integration or rules)
- [ ] Tests
    - [ ] API unit/integration tests (auth, RLS, quotas, proposals, exports)
    - [ ] Webhook signature verification tests
     - [ ] Subscription lifecycle tests:
         - Cancel user with admin org → after current_period_end, org is downgraded and paywall enforced.
         - Transfer admin to paying user → org immediately upgraded; transfer to free user → org downgraded.
         - Coupon applied → tier/limits reflect promotion during validity window.
    Why: API is the single source of truth; enforces security and business rules.
    Interacts with: DB RLS (via session middleware), Stripe, AI providers, SPA SurveyJS.
    Contract examples:
        - Planner: input {grant_url|text_spec}; output {sections:[{id,title,inputs[]}], schema_version}
        - Writer: input {proposal_id, section_id, answers, file_refs[]}; output {draft_text, assets[], tokens_used}
        - Revisions: input {proposal_id, section_id, change_request}; output {draft_text, diff}
    Security: JWT + role checks; idempotent webhooks; rate limiting on AI endpoints; file type/size validation.

4) AI Providers and Abstractions
- [ ] Provider abstraction (GPT-4o, Gemini; switch via env)
- [ ] Cost/latency logging per request
- [ ] Safety filters (max tokens, rate limiting per plan)
- [ ] Deterministic sampling settings for exports where possible
 - [ ] RAG store (templates + exemplars) to guide Planner/Writer prompts
     - [ ] Curate sample proposals and section templates (self-hosted data only)
     Why: Hybrid model minimizes cost while keeping quality; RAG stabilizes structure/voice.
     Interacts with: ai.* endpoints, quota middleware, exports (for deterministic render).
     Contract: Provider interface generate(prompt, opts) returns {text, usage, model_id}.
     Security: PII redaction rules in prompts where feasible; audit logs of prompts/responses.

5) Export Pipeline (Deterministic)
- [ ] Canonical renderer: Proposal JSON → Markdown
- [ ] Markdown → DOCX (pandoc or python-docx) and → PDF (pandoc or weasyprint)
- [ ] Asset embedding (images/diagrams) and stable paths
- [ ] Idempotency tests (same input → same output)
    Why: Single canonical Markdown avoids divergence across formats.
    Interacts with: proposals.content JSONB, files storage, AI diagram outputs.
    Contract: POST /exports creates job {id,status,url_when_ready}; outputs stored with content hash.
    Security: Validate access before generating/downloading; clean temp files.

6) Frontend (React SPA)
- [ ] Scaffold SPA (Vite or CRA) + routing + state mgmt
- [ ] Auth flow (OAuth callback, token storage, logout)
- [ ] Dashboard
    - [ ] My proposals list + create new
    - [ ] My organizations list with role badges
    - [ ] Profile edit (email, name)
- [ ] Proposal authoring flow (SurveyJS)
    - [ ] Load section plan from API
    - [ ] Per-section Q&A; send inputs to Writer API
    - [ ] Show AI draft vs previous content (diff view)
    - [ ] Approve/request changes; autosave JSONB state
    - [ ] File uploads per section; OCR status display
    - [ ] Finalization step when last section approved
- [ ] Exports UI
    - [ ] Trigger export (md/docx/pdf) + progress + download
- [ ] Paywall/upgrade
    - [ ] Enforce free-tier limits; CTAs for upgrade
    - [ ] Link to Stripe customer portal
    - [ ] Landing page buttons wired to checkout
- [ ] Analytics + consent
    - [ ] Umami integration
    - [ ] Cookie/consent notice if required
- [ ] SPA tests (unit + a few Playwright e2e flows)
    Why: Single source of truth is proposal JSON; SPA reflects and drives that state.
    Interacts with: Auth/JWT, proposals API, AI endpoints, exports, Stripe portal.
    Contract: SPA stores minimal local state; rehydrates fully from proposal JSON.
    Security: Avoid storing secrets in localStorage; CSRF safe patterns for uploads.

7) Proxy and Networking (Coolify + Traefik)
- [ ] Use Coolify-managed Traefik as reverse proxy (TLS via Let's Encrypt)
- [ ] Routes: domain root → SPA, /api → Django service; /static and /media served by API container
- [ ] Define Traefik labels (if needed) or configure via Coolify UI
- [ ] CORS and security headers (CSP, HSTS in prod): set via Traefik middlewares and API settings
    Why: Coolify standardizes deployment with Traefik handling routing and certificates.
    Interacts with: SPA asset hosting, API, file uploads, analytics endpoint.
    Security: Strict CSP with allowlists; gzip/brotli; large body limits for uploads only; HTTPS enforced.
    Deployment note: For MVP, prefer single-app topology (SPA built into API image) to avoid cross-origin and complex router rules; move to separate SPA/API apps later if scaling requires.

8) Operations and Security
- [ ] Secrets management (env vars documented; no keys in repo)
- [ ] Backups (Postgres volume + uploaded files)
- [ ] Basic monitoring/logging (structured logs; health endpoints)
- [ ] Security baseline
    - [ ] Dependency scan (pip/npm)
    - [ ] Auth brute-force rate limiting
    - [ ] Data retention/privacy review; update privacy page
    - [ ] RLS review and least-privileged DB user
    Why: Early testers still need resilience and data safety.
    Interacts with: CI/CD, DB, file store, privacy/legal docs.
    Contract: Daily backups verified restore; health endpoints used by uptime monitors.

9) Billing (Stripe) — Acceptance Tests
- [ ] New signup → checkout → active subscription reflected in app
- [ ] Downgrade/cancel → plan changes at period end
- [ ] Free → paywall reached → upgrade CTA works
- [ ] Webhooks verified and recover on retries
 - [ ] Admin cancels → org downgraded at period end (no perpetual tier carryover)
 - [ ] Admin transfer recomputes org tier instantly
    Why: Confident subscription lifecycle handling incl. proration and failures.
    Interacts with: Quota middleware, UI paywall, Subscriptions table, email notices (optional).
    Contract: Webhook processing is idempotent; status in DB matches Stripe.

10) Release Readiness (Early Testers)
- [ ] Smoke test checklist (install, signup, create org, author one proposal, export all formats)
- [ ] Seed demo content (optional)
- [ ] Onboarding doc for testers + feedback channel
- [ ] Changelog for MVP
- [ ] Deploy to test environment (compose) and capture runbook
 - [ ] Rewrite project README for full app (replace landing-only): overview, architecture, local dev, env vars, Coolify/Traefik deployment, CI, backups, security/RLS, Stripe/webhooks, AI limits, troubleshooting
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