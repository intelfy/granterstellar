[[AI_CONFIG]]
FILE_TYPE: 'TASK_LIST'
IS_SINGLE_SOURCE_OF_TRUTH: 'TRUE_EXCEPT_DEFER_TO_COPILOT-INSTRUCTIONS'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Outline current priorities', 'Detail next steps', 'Track remaining issues', 'Guide development and ops tasks']
PRIORITY: 'CRITICAL'
[[/AI_CONFIG]]

# Granterstellar — Engineering Plan (updated 2025-09-08)

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

- [x] Expanded Postgres-only matrix (creator/admin/member/anon + usage endpoint) — new `db_policies/tests/test_rls_usage_endpoint.py` covers `/api/usage` HTTP-level RLS. Least-privileged DB user + migration ownership guidance documented in `docs/rls_postgres.md` (sections: "Least-privileged DB user" and "Least Privilege & Migration Ownership").

### 3. Ops and monitoring

- [x] Minimal liveness `/api/health` and readiness `/api/ready` endpoints added; runbook & README updated.
- [~] Re-run dependency/SAST scans and capture deltas (infrastructure & automation added; pending: formal triage doc + suppressions rationale if needed).

## 4. AI providers

- [~] Safety filters (implemented: per-minute rpm, daily request cap, monthly token cap; tests in `ai/tests/test_ai_caps.py`; deployment guide updated with env vars; pending: deterministic sampling toggle + provider timeout/retry + prompt shield + pre-execution token projection to block before provider call). New env vars:
  - AI_RATE_PER_MIN_FREE / AI_RATE_PER_MIN_PRO / AI_RATE_PER_MIN_ENTERPRISE
  - AI_DAILY_REQUEST_CAP_FREE / AI_DAILY_REQUEST_CAP_PRO / AI_DAILY_REQUEST_CAP_ENTERPRISE
  - AI_MONTHLY_TOKENS_CAP_PRO / AI_MONTHLY_TOKENS_CAP_ENTERPRISE
  - AI_ENFORCE_RATE_LIMIT_DEBUG=1 (enforce in DEBUG for local testing)
  Response headers on 429: Retry-After, X-AI-Daily-(Cap|Used), X-AI-Monthly-Token-(Cap|Used) as applicable.
- [~] Deterministic sampling toggle for export-critical runs (env: `AI_DETERMINISTIC_SAMPLING`, default True; affects `/api/ai/format` deterministic flag). Pending: extend to write/revise variance controls if needed.
- [ ] RAG store (templates/samples); curate initial self-hosted set
- [ ] Prepare batch task & prompts for Gemini-2.5-Flash to twice a week search web for templates and successful/winning proposal samples for common grant calls we don't currently have templates for and integrate them into the RAG. Files should be categorized as either samples or templates. Log all new files added.
- [ ] Implement AI/user interaction flow: The user provides the open call they're applying for --> The planner (using web search to review the user's input URL for the open call and compares against templates/samples in the RAG) determines what sections will be needed and what information should be prefilled (drawing also from the organization metadata like name/description) and what questions to ask the user per section --> The writer parses the user's answers per section and fleshes out the section for review/revision until user approves --> the user is asked the next set of questions for the next section --> the writer repeats --> ... --> once all pre-planned sections are done, the user approves the text a final time, before the formatter structures it (prioritizing a good looking PDF formatting) according to a template (if one exists) or inference and similar sample writing and web search grounding (if a template does not exist) --> Formatter presents a mockup of the final .PDF versio of the file, formatted to closely resemble the templates/samples in layout --> The user exports the formatted file in their chosen extension, (or opens the editor and is asked which section they would like to edit, and whether they would like to edit the raw text manually or rerun the AI interactions for that section)
  
### NEW: Alpha-Critical Gaps (must complete before end-to-end testable AI flow)

These clarify that USERS NEVER SUPPLY PROMPTS DIRECTLY — backend owns role-specific prompt engineering.

- [x] Prompt Template System (High) — Implemented via `AIPromptTemplate` (name, version, variables, checksum auto-recomputed). Snapshots stored on `AIJobContext` (`rendered_prompt_redacted`, `prompt_version`, `template_sha256`).  
- [ ] Role-Specific Prompt Contracts (High) — Define strict input schema per role:  
  - Planner receives ONLY `{grant_url, grant_call_text?, org_profile}` and must output JSON schema: `{schema_version, sections:[{id,title,questions:[...] }]}`.  
  - Writer receives `{section_id, section_title, answers, approved_section_summaries[], memory[], retrieval_snippets[], file_refs[]}` and produces plain markdown draft text only.  
  - Reviser receives `{base_text, change_request, memory[], retrieval_snippets[], file_refs[]}` and returns revised text + structured diff object.  
  - Formatter receives `{full_text, template_hint?, style_guidelines?, assets?, file_refs[]}` and returns formatted markdown canonical form (later rendered to PDF/DOCX).  
  Add validation: reject provider output if schema mismatch (fail early with clear error).  
- [x] AIJobContext / Prompt Audit (High) — Implemented: fields present (`template_sha256`, `redaction_map`, `model_params`, `snippet_ids`, `retrieval_metrics`). Deterministic redaction taxonomy + mapping persisted.  
- [ ] RAG Data Models (High) — Create `AIResource` (template|sample|call_snapshot), `AIChunk` (resource_fk, ord, text, embedding_key/vector, token_len, metadata: {section_hint, license, source_url, type}), migration + admin.  
- [ ] Embedding Service (High) — Integrate MiniLM-L6-v2 (sentence-transformers). Abstraction `EmbeddingService` with pluggable backend (dev: FAISS in tmp dir; prod: Mongo Atlas vector index). Provide `embed(texts) -> List[Vector]` + health check.  
- [ ] Chunking & Ingestion Pipeline (High) — Celery task: fetch grant URL → clean HTML → produce call_snapshot resource → chunk & embed; ingestion for curated templates/samples (YAML manifest). Deduplicate by sha256(text) prefix & similarity (cosine >0.97).  
- [ ] Retrieval Integration (High) — Planner: semantic match templates/samples by call text & org profile → include matched template IDs & rationale in planner prompt. Writer/Reviser: top-k snippet retrieval gated by token budget. Implement dynamic token budgeting (reserve % for user answers & memory).  
- [ ] Dynamic Question Generation (High) — Planner populates `questions` per section using retrieved template question banks + gap analysis of org metadata vs template required fields. Provide deterministic fallback set when retrieval empty.  
- [ ] Memory Injection Upgrade (High) — Replace underscore hack with explicit memory field in writer/reviser prompt assembly; add scoring (usage_count + recency decay) and token truncation.  
- [ ] Section Workflow Model (High) — Add `ProposalSection` model (proposal_fk, section_id, state=draft|approved, draft_text, approved_text, revisions JSON (list), updated_at). Migrate existing proposal `content` into sections mapping.  
- [ ] Revision Diff Engine (High) — Implement paragraph/semantic diff (rapidfuzz) returning JSON blocks with change types; integrate into revise task (replace "stub").  
- [ ] Quota Binding to AI Usage (High) — Map each approved section (first approval) to proposal usage increment; enforce cap before enqueue write/revise if section already approved (unless revision). Track token usage per section in metrics.  
- [ ] Token & Phase Metrics (High) — Extend `AIMetric` or new `AIPhaseMetric` to capture retrieval_ms, embedding_ms, prompt_tokens, completion_tokens, snippet_count, memory_count.  
- [ ] Provider Fallback & Circuit Breaker (High) — Wrap calls: on model failure/timeouts escalate to secondary provider; maintain failure counters; open circuit after threshold.  
- [ ] Prompt Safety / Injection Shield (High) — Pre-flight scan of user answers & memory for disallowed directives (regex list) + neutralization; log events; abort with safe error.  
- [x] PII Redaction Layer (High) — Deterministic category tokens `[CATEGORY_hash]` (EMAIL, NUMBER, PHONE, ID_CODE, SIMPLE_NAME, ADDRESS_LINE) with persisted `redaction_map`. Follow-ups: monitoring metrics, admin review UI.  
- [ ] Context Budget Manager (High) — Central utility that given model max_tokens & reserved output tokens returns trimmed sets: retrieval snippets, memory items, file refs. Ensures deterministic ordering & annotation.  
- [ ] Retrieval Caching (Medium) — Cache (grant_call_hash, section_id) → snippet IDs for TTL 24h to reduce re-embedding cost; bust on new resource ingestion.  
- [ ] Scheduled RAG Refresh (Medium) — Celery beat: 2x weekly run ingestion tasks for new public grant calls list; summary log with counts (added, duplicates, failed).  
- [ ] Re-Embed Drift Task (Medium) — If embedding model version changes, queue re-embed for all resources (batch throttled).  
- [ ] Cleanup & TTL (Medium) — Purge AIJob + AIJobContext older than 30 days; archive metrics.  
- [ ] E2E Alpha Test Suite (High) — New test path: simulate user providing only URL → expect full section question plan → iterative answer & write cycle → revise → approve → format → export PDF stub. Includes assertions for prompt_version and retrieval snippet references.  
- [ ] Documentation: Add `docs/ai_prompts.md` describing role contracts, variable semantics, safety policy; warn that direct user prompt injection is unsupported.  

- [ ] (Follow-up) Semantic Rerank (Low) — Cross-encoder rerank top 30 retrieval, keep best 6.
- [ ] (Follow-up) Streaming Writer (Low) — SSE endpoint streaming partial drafts (gated by provider support).

- [ ] Test: planner schema validation rejects malformed provider JSON.
- [ ] Test: writer rejects output containing JSON or non-markdown gating markers.
- [ ] Test: diff engine returns added/removed counts > 0 when change_request supplied.
- [ ] Test: quota denial when cap reached before new section write.
- [ ] Test: prompt audit row created & redacted fields masked.
- [ ] Test: injection shield blocks disallowed directive phrase.
- [ ] Test: retrieval fallback path (no snippets) still plans sections.
- [ ] Test: memory scoring excludes aged low-usage items after threshold.

- [x] Implement AI memory per user/org (model `AIMemory` + suggestions endpoint `/api/ai/memory/suggestions`) with automatic capture on write/revise and integration into provider prompt context.
  - Storage: Idempotent dedup via `(created_by, org_id, key_hash, value_hash)` uniqueness; per‑scope retrieval with strict isolation (org memories excluded from personal unless `X-Org-ID` header supplied).
  - Prompt integration (2025-09-08): `write` injects top (limit 3) suggestions under reserved answer key `_memory_context` as a `[context:memory]` block; `revise` appends `[context:memory]` block to `change_request`. Underscore key prevents recursive persistence.
  - Frontend: Hook `useAIMemorySuggestions` + `MemorySuggestions` component already surfaced in AuthorPanel (chips → click to insert); tests in `ai-memory-suggestions.test.jsx` (section filter, org filter, limit, empty token, refresh) all passing.
  - Tests: Added `test_memory_prompting.py` (write/revise inclusion + absence when none). AI test suite now 37 tests green (was 34). Web suite 18 files / 30 tests green.
  - Observability: Future enhancement could expose whether memory context applied via response metadata header (deferred).
  - NOTE (flake observed once pre-final code): A single transient failure of `test_org_scope_isolated_from_personal` (org memory leaked to personal) during an earlier run before final code reload; not reproducible after latest changes. Added follow-up backlog item to monitor.
  - Follow-up (backlog): configurable token truncation (currently value[:400]), per-key weighting, and provider contract evolution to accept structured memory context separately from answers.

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
  - [ ] API image sanity: `DEBUG=0`, required envs present, correct port exposed, healthcheck paths wired (`/api/health` liveness, `/api/ready` readiness)
  - [ ] Optional: build API with `STRIP_PY=1` and confirm no `.py` in final image (keeps IP hardening aligned)
  - [ ] SPA build stage outputs hashed assets under `/static/app/` with base `/app`; confirm no source maps

- Coolify app definitions
  - [ ] Define services: API, SPA static (or landing), Postgres, optional Redis (Celery/async)
  - [ ] Attach Traefik routes for `/`, `/app`, `/api`, `/static/app/`, `/media/` as per routing map
  - [x] Configure environment variables (PROD) end-to-end — authoritative matrix now in `docs/ops_coolify_deployment_guide.md` (kept in sync)
  - [ ] Health checks: API GET `/api/health`; readiness GET `/api/ready`; static GET `/` (or `/app/`)

- PROD environment variables (must set)
  - [x] Core: `SECRET_KEY`, `ALLOWED_HOSTS`, `PUBLIC_BASE_URL`, `DATABASE_URL`, `REDIS_URL` (if async)
  - [x] Security: `SECURE_*`, `SESSION_*`, `CSRF_*`, `CSP_*` (Script/Style/Connect allow-lists minimal)
  - [ ] OAuth: `GOOGLE_*`, `GITHUB_*`, `FACEBOOK_*`, `OAUTH_REDIRECT_URI`, JWKS/issuer where needed
  - [x] Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, prices `PRICE_*` (enterprise placeholder noted)
  - [ ] Async toggles: `EXPORTS_ASYNC`, `AI_ASYNC`, `CELERY_*` (if used)
  - [ ] SPA: `VITE_BASE_URL`, `VITE_API_BASE`, `VITE_ROUTER_BASE=/app`, optional `VITE_UMAMI_*`
  - [x] Uploads/OCR, Quotas, AI provider keys per `.github/copilot-instructions.md`

- Docs refresh — install_guide.md (idiot-proof)
  - [ ] Update `docs/install_guide.md` referencing new env matrix (avoid duplication)
  - [ ] Include screenshots of critical steps (variables, routes, health checks), and a copy-paste env block template
  - [ ] Post-deploy validation checklist: health endpoints, CSP errors absent, OAuth login, Stripe webhook received, file upload OK

### NEW: Environment Doctor & Consistency

- [ ] Implement `manage.py env_doctor` command:
  - Validates production invariants (SECRET_KEY not default, ALLOWED_HOSTS no `*`, CORS_ALLOW_ALL=0 when DEBUG=0)
  - Ensures conditional groups complete (Stripe, OAuth, Redis/Celery, AI provider)
  - Warns JWT_SIGNING_KEY == SECRET_KEY in prod
  - Lists unset optional security hardening vars (CSP_* when analytics configured)
  - Exits non-zero on hard errors; zero with warnings for advisory gaps
- [ ] Add CI step invoking `python manage.py env_doctor --strict` (DEBUG=0 simulation) using a sample `.env.ci` to prevent regressions
- [ ] Document env doctor usage in deployment guide (link to command section) once implemented

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

### Recently Completed (2025-09-08)

- Formatter blueprint injection (conditional append of instructions + sorted JSON schema for role `formatter`).
- Template drift detection function with DB refetch; test `test_context_includes_checksum_and_drift_detection` green.
- Automatic checksum recomputation on template save to avoid stale comparisons.
- Deterministic redaction taxonomy + persisted `redaction_map` enabling reproducible audits.

### Follow-Up (Prompt Governance)

- [ ] Drift metrics aggregation (count drifted templates / 24h) & admin report.
- [ ] Redaction coverage metric (tokens per category) for anomaly detection.
- [ ] Negative control drift test (unchanged template after unrelated field update).
- [ ] Admin UI: view original vs redacted prompt snapshot + category legend.
- [ ] Blueprint schema lint (ensure stable ordering, max size guard) in CI.
- [ ] Optional: redact_map diff tool if taxonomy expands.

Database

- [ ] Optional UsageEvents (AI metering)

Backend/API

- [ ] Proposals: versioning metadata on PATCH
- Prompt shield: [ ] central prompts + basic injection screening

Dependency & Supply Chain

- [ ] Add Python constraints/lock (pip-tools compile → requirements.txt + constraints.txt)
- [ ] Commit npm lockfile and enforce `npm ci` (update Docker build)
- [x] CI: add pip-audit & npm audit (prod deps) failing on HIGH/CRITICAL (heuristic gating v1; precise JSON severity parsing task open)
- [x] Weekly automated dependency updates (Dependabot config at `.github/dependabot.yml` — grouped minor/patch + dev deps)
- [x] Generate SBOM (CycloneDX) for Python & JS in CI and archive artifact
- [ ] Document dependency triage workflow in `docs/ops_runbook.md`

API Hardening & Auth

- [ ] Scoped throttle for login (`throttle_scope="login"`) + test brute-force attempts
- [ ] Implement lockout (username+ip) after configurable failed attempts (exponential backoff)
- [ ] Remove SessionAuthentication from DRF defaults (retain for admin only)
- [ ] Explicit AllowAny only on public endpoints; audit others (add test)
- [ ] Startup environment validation (critical vars) fail-fast when DEBUG=0
- [ ] Add DRF pagination defaults (DEFAULT_PAGINATION_CLASS, PAGE_SIZE) and adjust list views

Structured Logging & Observability

- [ ] Request ID middleware + log propagation
- [ ] Introduce structured JSON logs (structlog or stdlib formatter) with core fields
- [ ] Timing middleware emits duration_ms field
- [ ] Redact PII (emails, tokens) from logs; add test
- [ ] Upload rejection log includes reason + request_id (test)

Exports & Integrity

- [ ] Guard: abort export if generated artifact exceeds size/page thresholds
- [ ] Add checksum verification endpoint or `?verify=1` to re-hash artifact
- [ ] Store & return export size metadata
- [ ] Cleanup task for stale/failed export jobs

AI Providers (additional)

- [ ] Per-provider timeout & retry (circuit breaker counters)
- [ ] Token usage accounting scaffold
- [x] Prompt redaction layer (strip PII) before logging — covered by deterministic redaction taxonomy.

RLS & Roles Model

- [ ] Replace `is_staff` role inference with explicit user/org role resolver
- [ ] Extend role matrix (OWNER, ADMIN, MEMBER) – migration plan with backward compat
- [ ] Tests ensuring staff flag alone does not elevate RLS access

Data & Privacy

- [ ] PII classification document (fields, retention) added to docs
- [ ] Implement user data export & delete endpoints + tests
- [ ] Redact user identifiers in structured logs (configurable override in DEBUG)
- [ ] Add backup encryption guidance (GPG/KMS) to `security_hardening.md`

Performance / Caching (API additions)

- [ ] ETag/Last-Modified headers for proposal detail (hash of updated_at)
- [ ] Validate gzip/br served (integration test) via reverse proxy or middleware
- [ ] Bootstrap aggregate endpoint (account+orgs+usage) cached short-term

Testing Enhancements (supplemental)

- [ ] Security headers test (DEBUG=0) asserting CSP/HSTS/COOP/CORP
- [ ] Throttle & lockout tests (login, file upload)
- [ ] Pagination test ensures default page size & navigation keys
- [ ] Export checksum stability test (md/pdf/docx)
- [ ] RLS negative test for cross-org leakage attempt

Container & Build

- [ ] Parameterize gunicorn workers (`WEB_CONCURRENCY`)
- [ ] Set reproducible build env (`PYTHONHASHSEED=0`) in Dockerfile
- [ ] Extend STRIP_PY test to cover new modules added
- [ ] Multi-arch build documentation

## 12 i18n Readiness (pre-design hardening)

Goal: Centralize ALL user-facing strings before visual redesign to avoid churn; establish translation pipeline & enforcement. Users should never see unfrozen copy outside keys store.

Phases

- [ ] Inventory & Classification — Script: scan `web/src/**/*.{ts,tsx,js,jsx}` + root HTML pages for probable user-facing literals (regex: words with spaces, exclude ALL_CAPS, URLs, variables). Output CSV: file, line, original_text, hash.
- [ ] Key Namespace Design — Adopt convention `area.component.purpose` (e.g., `auth.login.button_submit`). Document in `docs/design_system.md` (i18n section) and add linter rule description.
- [ ] Minimal Runtime Layer — Implement lightweight `t(key, fallback?)` + `useT()` hook with TypeScript key union generated from JSON schema. No heavy lib yet (keep bundle small); future-compatible with ICU messages.
- [ ] Messages Store Scaffold — Create `web/src/locales/en/messages.json` (flat map) + generation script to sort keys alphabetically & validate collisions.
- [ ] Extraction Tooling — Node script: replaces raw literals (approved list) with `t('...')`; emits diff summary (# replaced, skipped). Manual review required for ambiguous strings (length < 4, dynamic templates, placeholders).
- [ ] Placeholder & Interpolation — Implement simple `{name}` variable substitution using template function `t.key('auth.greeting', {name: userFirstName})` with compile-time key checking.
- [ ] HTML & Django Templates Pass — Extract strings from `index.html`, landing pages, simple Django templates (if any user-facing). Replace with placeholders pulling from a preloaded JSON (inline script tag `window.__LOCALES__`).
- [ ] Backend i18n Scaffold — Add `locale/` with `django-admin makemessages` config (even if EN only). Ensure `USE_I18N=True`. Add extraction make target.
- [ ] Enforcement ESLint Rule — Custom rule or config: forbid string literals in JSX children unless wrapped in `t()` (allow list for a11y attributes, test files). Failing CI if new violations.
- [ ] CI Guard — Job: run extraction diff; if new raw strings detected (not in allowlist), fail with guidance.
- [ ] Progress Metric — Script counts (% externalized = externalized / (externalized + remaining_detected)). Print badge in CI logs.
- [ ] Accessibility Synergy — Integrate axe-core scans (dashboard, proposal editor, billing, uploads) after strings externalized to ensure labels preserved.
- [ ] Docs — Add `docs/i18n.md`: philosophy, key naming, extraction workflow, adding new strings checklist.
- [ ] Post-Extraction Cleanup — Remove duplicate or unused keys (script: reference count across source; warn unused >30 days).
- [ ] Future (Deferred) — Add locale switcher UI + language negotiation (Accept-Language) + crowd/managed translation pipeline.

Tests

- [ ] Test: extraction script produces deterministic hash for unchanged files.
- [ ] Test: ESLint rule flags inline string in JSX.
- [ ] Test: interpolation `{name}` replaced correctly and escapes HTML.
- [ ] Test: fallback returns key when missing translation (and logs once).
- [ ] Test: progress metric output >= previous run (non-regression) or explicitly annotated decrease.

Housekeeping

- [ ] Add CODEOWNERS (billing/, db_policies/, middleware, ai/)
- [ ] Update CONTRIBUTING with dependency/security update cadence
- [ ] Add `scripts/env_doctor.py` (invoked pre-test in CI)
- [ ] Optional Makefile with standard targets (lint, test, build, doctor)

Security Hardening (new audit additions)

- [ ] DRF: enforce authenticated default permission (remove DEBUG AllowAny fallback); explicit AllowAny only per public view
- [ ] Startup assertion: abort if DEBUG=1 and non-local host in `ALLOWED_HOSTS`
- [ ] JWT: require distinct `JWT_SIGNING_KEY` in production (error if identical to SECRET_KEY)
- [ ] CSP reporting: add `CSP_REPORT_URI` + `CSP_REPORT_ONLY` envs; implement report-only mode toggle
- [ ] Virus scan command tests (invalid chars, disallowed binary, timeout) ensuring fail-closed behavior
- [ ] Add safeguard for large OCR durations (timing + warn log > threshold)

Exports

- [ ] Asset embedding (images/diagrams) with stable paths

Frontend (SPA)

- [ ] Integrate SurveyJS for authoring

 

Proxy/Networking

- [ ] Coolify/Traefik labels or UI config as required; document

Operations & Security

- [ ] Basic metrics: request latency, AI invocation duration, Celery task success/fail counts (expose /metrics if/when Prometheus planned)

Maintainability & Refactors

- [ ] Split monolithic `settings.py` into logical modules (security, storage, billing) or adopt split-settings (incremental)
- [ ] Extract billing webhook helpers into `billing/services.py` with dedicated unit tests (idempotency + discount + bundle credits)
- [ ] Centralize file security helpers (`_is_under_media_root`, signature checks) in a shared util module + tests

Test Coverage Additions

- [ ] Test: production DRF default permission remains IsAuthenticated
- [ ] Test: CSP header forbids inline styles unless `CSP_ALLOW_INLINE_STYLES=1`
- [ ] Test: webhook signature required when DEBUG=0 (invalid signature → 400)
- [ ] Test: virus scanner invalid command returns `scan_error`
- [ ] Test: file upload throttle (after implementing) returns 429 on rapid bursts
- [ ] Test: JWT_SIGNING_KEY enforcement (prod simulation)
- [ ] Test: structured logging emits expected keys for upload rejection
- [ ] Test: OCR large file skipped when size > TEXT_EXTRACTION_MAX_BYTES
- [ ] Test: add i18n extraction smoke (no duplicate msgids) once scaffolding added

## Notes

- Keep Markdown as canonical export. Prefer async for long AI/exports. Maintain RLS correctness; enforce quotas consistently with `X-Org-ID` and role checks.
- When docs and code diverge, update both and reflect deltas here briefly.
