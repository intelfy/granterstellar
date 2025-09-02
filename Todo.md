# Granterstellar — Engineering Plan (updated 2025-09-01)

Source of truth for product/architecture: `.github/copilot-instructions.md` and `docs/README.md` (install/security/ops details in `docs/*`). This file tracks current priorities and gaps only.

Legend: [ ] todo, [~] in progress, [x] done

## Status snapshot

- API stable: accounts/orgs/proposals/files/exports/billing/ai; JWT + Google/GitHub/Facebook OAuth; quotas + seats/extras; exports md→pdf/docx; AI plan/write/revise/format (sync or async); uploads hardened (size/MIME/magic/scan); DEBUG flows for local dev.
- SPA stable: auth/RequireOrg, proposals list/create, orgs + invites, uploads, AI flows incl. final-format, exports, paywall/upgrade, base path `/app`, minimal styling. Route-level code splitting in place for major pages. Editor includes AuthorPanel (metadata + internal notes) and SectionDiff (inline diff). Unit tests pass; jsdom guards in place.
- Security: strict CSP, Host/cookie/rate limits, OAuth state/JWKS, SSRF guards, safe external nav, webhook signature in non-DEBUG. Backups scripted; orphan scan present.
- Tests: API/Web suites green locally; RLS suite green against Postgres via task. CI covers API/Web/Docs. Linting passes (ruff, eslint-js).

## Current priorities (August–September 2025)

### 1. Stripe promotions live-mode E2E

- [~] Verify coupons/promo codes in staging/prod (signed webhooks) and ensure `/api/usage` reflects active discounts end-to-end.

### 2. RLS coverage and DB hardening

- [~] Expand Postgres-only matrix (creator/admin/member/anon) and document least-privileged DB user + migration policy notes in docs.

### 3. Ops and monitoring

- [x] Minimal health/monitor endpoint `/api/healthz` added; review logs and runbook still pending.
- [ ] Re-run dependency/SAST scans and capture deltas (document compensating controls; add minimal suppressions if justified).

## 4. AI providers

- [ ] Safety filters (max tokens, plan rate limits)
- [ ] Deterministic sampling toggles for export-critical runs
- [ ] RAG store (templates/samples); curate initial self-hosted set
- [ ] Prepare batch task & prompts for Gemini-2.5-Flash to twice a week search web for templates and successful/winning proposal samples for common grant calls we don't currently have templates for and integrate them into the RAG. Files should be categorized as either samples or templates. Log all new files added.
- [ ] Implement AI/user interaction flow: The user provides the open call they're applying for --> The planner (using web search to review the user's input URL for the open call and compares against templates/samples in the RAG) determines what sections will be needed and what information should be prefilled (drawing also from the organization metadata like name/description) and what questions to ask the user per section --> The writer parses the user's answers per section and fleshes out the section for review/revision until user approves --> the user is asked the next set of questions for the next section --> the writer repeats --> ... --> once all pre-planned sections are done, the user approves the text a final time, before the formatter structures it (prioritizing a good looking PDF formatting) according to a template (if one exists) or inference and similar sample writing and web search grounding (if a template does not exist) --> Formatter presents a mockup of the final .PDF versio of the file, formatted to closely resemble the templates/samples in layout --> The user exports the formatted file in their chosen extension, (or opens the editor and is asked which section they would like to edit, and whether they would like to edit the raw text manually or rerun the AI interactions for that section)
- [ ] Implement AI memory per user (user uploads persisted in "My files" unless deleted, commonly given user answers persisted in database and suggested on sections - such as the user giving a budget in one proposal and it being suggested automatically when writing the next - etc.)

### 5. Performance & optimization (pre-deploy)

- Web build (Vite)
  - [~] Ensure production build has: sourcemap=false, minify on, CSS minify, hashed filenames, asset inlining threshold sensible
  - [x] Drop console/debugger in prod build (keep aligned with CI invariants); verify via CI grep against `web/dist`
  - [x] Route-level code splitting: React.lazy for heavy views (dashboard/proposals/orgs, account, billing) implemented; further tuning pending
  - [x] Vendor chunking and stable manualChunks to maximize browser cache reuse
  - [ ] Preload critical above-the-fold chunks; lazy-load secondary panels (OCR, metrics)
  - [ ] Analyze bundle (rollup-plugin-visualizer) and cap main bundle size; document deltas
  - Baseline (2025-09-01 local): total gzipped JS ≈ 59.8 KB; largest chunk vendor-react ≈ 43.7 KB gzip. Analyzer report at web/dist/stats.html. CI guard wired via scripts/sizeguard.mjs with budget 600 KB (soft; tighten later to ~180–250 KB as features stabilize).

- Runtime (client)
  - [ ] Coalesce and debounce autosaves/searches; cap concurrency for background fetches; exponential backoff on retry
  - [ ] In-memory cache for GETs (SWR-style) on stable resources: `/api/usage`, `/api/orgs/*`, proposal lists
  - [ ] Avoid long lists re-rendering; memoize selectors; virtualize if >100 rows
  - [ ] Remove unnecessary history.replaceState usage; prefer router navigation (already started)

- API efficiency
  - [ ] Ensure list endpoints are paginated and indexed (confirm `select_related/prefetch_related` on proposals/orgs)
  - [ ] Add/verify gzip/br compression and ETag/Last-Modified for cacheable GETs
  - [x] Cache lightweight, per-user/org GETs (e.g., `/api/usage`) briefly in Redis with RLS-aware keys (user+org)
  - [ ] Batch endpoints where reasonable (e.g., combined bootstrap: account, orgs, usage)

- Infra/delivery
  - [ ] Serve `web/dist` via Coolify/Traefik with gzip+br; long-lived immutable cache headers on hashed assets
  - [ ] Optional CDN in front of static if needed; document invalidation strategy

- Guardrails & SLOs
  - [x] Add CI check: build SPA and assert no source maps, no console/debugger, and bundle size thresholds
  - [ ] Define targets: p95 TTI < 2.5s (desktop fast 3G throttling), main bundle < 180KB gzip, total blocking time < 200ms
  - [ ] Add a lightweight Web Vitals reporting hook (debug only) to spot regressions pre-prod

### 6. IP protection (release hardening)

- SPA artifacts
  - [x] No source maps in prod (`build.sourcemap=false`), remove inline `sourceMappingURL` comments
  - [x] Strip comments from JS/CSS; configure Terser `format.comments` to preserve third‑party license banners (e.g., `/@license|@preserve|^!/`)
  - [x] Drop `console`/`debugger` and dev-only branches in prod builds; verify via CI grep
  - [ ] Exclude docs/tests/maps and any non-runtime assets from `web/dist`

- API container
  - [ ] Build with bytecode-only: enable Docker build arg `STRIP_PY=1` to compile `.py` → `.pyc` and remove sources
  - [ ] Multi-stage image that excludes `docs/`, `tests/`, examples, and tooling not needed at runtime
  - [ ] Ensure DEBUG off, detailed tracebacks disabled in prod; version endpoints return minimal info

- Verification in CI
  - [x] Step: build SPA and assert no `*.map`, no `sourceMappingURL`, no `console|debugger` strings
  - [x] Step: build API image with `STRIP_PY=1` and assert no `*.py` present in final layer
  - [ ] License check: ensure license banners of third‑party code are retained where required

- Operator docs remain in private repo
  - [ ] Keep full documentation, annotations, and comments in the private repo and internal images only; ship minimal prod artifacts

### 7. Coolify validation (pre-deploy)

- Containers & builds
  - [ ] Verify Dockerfiles build successfully in Coolify (multi-stage where applicable); ensure only runtime artifacts ship
  - [ ] API image sanity: `DEBUG=0`, required envs present, correct port exposed, healthcheck path wired (e.g., `/api/healthz`)
  - [ ] Optional: build API with `STRIP_PY=1` and confirm no `.py` in final image (keeps IP hardening aligned)
  - [ ] SPA build stage outputs hashed assets under `/static/app/` with base `/app`; confirm no source maps

- Coolify app definitions
  - [ ] Define services: API, SPA static (or landing), Postgres, optional Redis (Celery/async)
  - [ ] Attach Traefik routes for `/`, `/app`, `/api`, `/static/app/`, `/media/` as per routing map
  - [ ] Configure environment variables (PROD) end-to-end (see list below); validate via Coolify variables UI
  - [ ] Health checks: API GET `/api/healthz`; static GET `/` (or `/app/`)

- PROD environment variables (must set)
  - [ ] Core: `SECRET_KEY`, `ALLOWED_HOSTS`, `PUBLIC_BASE_URL`, `DATABASE_URL`, `REDIS_URL` (if async)
  - [ ] Security: `SECURE_*`, `SESSION_*`, `CSRF_*`, `CSP_*` (Script/Style/Connect allow-lists minimal)
  - [ ] OAuth: `GOOGLE_*`, `GITHUB_*`, `FACEBOOK_*`, `OAUTH_REDIRECT_URI`, JWKS/issuer where needed
  - [ ] Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, prices `PRICE_*`
  - [ ] Async toggles: `EXPORTS_ASYNC`, `AI_ASYNC`, `CELERY_*` (if used)
  - [ ] SPA: `VITE_BASE_URL`, `VITE_API_BASE`, `VITE_ROUTER_BASE=/app`, optional `VITE_UMAMI_*`
  - [ ] Uploads/OCR, Quotas, AI provider keys per `.github/copilot-instructions.md`

- Docs refresh — install_guide.md (idiot-proof)
  - [ ] Update `docs/install_guide.md` with step-by-step Coolify deployment: create DB, add services, set envs, connect domains
  - [ ] Include screenshots of critical steps (variables, routes, health checks), and a copy-paste env block template
  - [ ] Post-deploy validation checklist: health endpoints, CSP errors absent, OAuth login, Stripe webhook received, file upload OK

### 8. Proxy/CSP and deploy routes (Coolify/Traefik)

- [ ] Finalize routes: `/` landing, `/app` SPA, `/api`, `/static/app/`, `/media/`. Confirm CSP allow-lists per env (incl. Umami host).

### 9. SPA tests (targeted)

- [x] E2E: deep-link across OAuth + register path.
- [x] Organizations standalone route renders and manage view (members/invites) wired.
- [x] AuthorPanel notes and SectionDiff rendering covered.
- [x] Authoring OCR upload previews and sends file_refs on write.

## Acceptance tests — Billing (Stripe)

- [ ] New signup → checkout → active subscription reflected in app
- [ ] Free → capped → upgrade CTA works and usage updates
- [~] Downgrade/cancel → plan changes at current_period_end
- Webhook behaviors covered by unit tests: seats scaling [x], extras bundles [x], admin transfer recompute [x]

## 10 Superadmin dashboard

- [ ] Minimal ops panel: quota overrides, webhook retry/sync, usage export, feature toggles, ban users/orgs, modify users/orgs, model switches; audit + IsSuperUser only. Must be COMPLETELY secure.

## 11 Front End Design (LAST STEP BEFORE DEPLOYING MVP)

- [ ] Paginate app into separate views with a sidebar navigation (list is non-exhaustive)
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

## Open backlog (scoped, non-exhaustive)

Database

- [ ] Optional UsageEvents (AI metering)

Backend/API

- [ ] Proposals: versioning metadata on PATCH
- Prompt shield: [ ] central prompts + basic injection screening

Exports

- [ ] Asset embedding (images/diagrams) with stable paths

Frontend (SPA)

- [ ] Integrate SurveyJS for authoring
- [ ] Extract user-facing copy into keys file (prep for styling/i18n)

Proxy/Networking

- [ ] Coolify/Traefik labels or UI config as required; document

Operations & Security

- [ ] Data retention/privacy pass; update privacy page

## Notes

- Keep Markdown as canonical export. Prefer async for long AI/exports. Maintain RLS correctness; enforce quotas consistently with `X-Org-ID` and role checks.
- When docs and code diverge, update both and reflect deltas here briefly.
