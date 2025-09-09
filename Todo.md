[[AI_CONFIG]]
FILE_TYPE: 'TASK_LIST'
IS_SINGLE_SOURCE_OF_TRUTH: 'TRUE_EXCEPT_DEFER_TO_COPILOT-INSTRUCTIONS'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Outline current priorities', 'Detail next steps', 'Track remaining issues', 'Guide development and ops tasks']
PRIORITY: 'CRITICAL'
[[/AI_CONFIG]]

# Granterstellar — Engineering Plan (updated 2025-09-09)

Source of truth for product/architecture: `.github/copilot-instructions.md` and `docs/README.md` (install/security/ops details in `docs/*`). This file tracks current priorities and gaps only.

Legend: [ ] todo, [~] in progress, [x] done

## Assumptions & Constraints (Alpha Focus)

Scope assumptions for the immediate Alpha Critical Path. Adjust here before coding if any change in product direction.

### Section Workflow

- A proposal is composed of an ordered list of sections (already implemented as `ProposalSection` with fields: `key` (slug), `order`, `state=draft|approved`, `draft_content`, `approved_content`, `revisions[]`, `locked`). Legacy `Proposal.content` mirrors approved content and will be deprecated after serializer pivot.
- Quota increments only on NEW proposal creation (not per section). Free tier: 1 lifetime proposal (deleting does NOT restore quota). Paid tiers: monthly new proposal cap (plan‑dependent). No active cap for paid tiers. Unlimited edits after creation (subject to rate limiting) but call URL immutable.
- Structure (section headers + order) is planned exactly once by the planner. Optional: a single "structure preview" step where user can request ONE revision (future enhancement; out of immediate scope). After lock, structure cannot change.
- Each section can be revised up to 5 times (diff revisions) regardless of overall proposal approval/export status; sections remain individually editable forever within the revision cap. (Current backend truncates at 50; explicit 5‑cap enforcement pending.)
- Revisions store structured diffs (target cap: 5 per section, 25 blocks each) plus revised snapshot; truncation logic reused from existing `append_revision` (currently allows up to 50 historical entries until enforcement lands).
- Migration: existing `Proposal.content` → single section `main` (order=1, state=approved if non-empty else draft) to preserve legacy content; ensures subsequent per‑section editing path.
- Approve action idempotent; duplicate approves are no‑ops.
- Unlock after approval permitted (user may continue revisions if quota remaining); promotion sets `state=approved` and `locked=True`; unlock path subject to future tightening if abuse observed.
- Section deletion / reordering not supported in alpha (avoids quota/accounting & diff complexity). Creating a new proposal is required for different structure.
- After proposal export, sections and metadata remain available for further AI-assisted revisions (within 5‑revision cap).

### Dynamic Question Generation & Planner Retrieval Flow

- Sources (priority order): 1) Grant-specific template(s) from RAG (matched via immutable `call_url` / grant identifier), 2) Grant-specific or closely similar sample winning proposals from RAG, 3) Agentic web search (to acquire missing templates/samples and immediately ingest), 4) Universal baseline grant template (only if RAG + search produce nothing), 5) Org metadata gaps (ask user to supply missing basics like mission if absent).
- Questions derive from required sections: if a section "Statement of Need" exists, at least one question targets that content explicitly.
- Types limited to plain free‑text or file uploads (no selects, ratings, etc.).
- Ordering: sections ordered as in highest quality template/sample (PDF order). Questions grouped under their section, preserving section order; within a section order by template priority then stable key.
- Planner runs exactly once; no re-planning. (Optional single preview revision deferred.) During first run it triggers asynchronous ingestion (embedding) of any newly discovered templates/samples so later writes/revisions benefit from retrieval.
- Fallback web search: if RAG empty for both template & sample queries, launch web search agent; any found assets are stored (raw original + extracted structured section outlines) and embedding tasks queued. If still none, use universal template (deterministic) and set `fallback_mode=true`.
- Audit: hash of ordered question keys + section slugs stored to detect drift.

### Memory Scoring & Injection

- Memory relevance: no temporal decay; score = `usage_count` only. User/org snippets & uploaded file summaries assumed persistently relevant until user deletes them.
- Top K=5 by score (ties: deterministic sort by id). Min score threshold 1 (remove prior 0.15 fractional heuristic) to eliminate nearly unused noise.
- Each memory item truncated to ~400 chars (hard cap) pre-provider.
- Injection: dedicated contextual block; providers must not echo memory back into persistent memory store to avoid duplication.
- If zero qualifying memories, omit block entirely.

### Provider Fallback & Circuit Breaker

- Timeouts: 25s write/format, 15s revise/plan (align with expected longer formatting latency). Deterministic deadlines support stable UX messaging.
- Retry: one immediate retry on timeout/5xx (validation or schema errors do not retry) then fallback provider invocation.
- Circuit: open after 5 qualifying failures within 120s; stay open 180s; half‑open allows 1 probe to close.
- Secondary provider must satisfy identical schema contract; double failure emits `AI_TEMPORARY_UNAVAILABLE` and logs failure taxonomy.

### Prompt Safety / Injection Shield

- Inputs scanned (case-insensitive) for directives altering model role/safety, e.g., /(ignore (previous|earlier) (instructions|rules)|system:|you are now)/.
- Redacts or rejects: If high-risk pattern found → reject with 422; low-risk (embedded inside sentence) → wrap with neutralizing comment token and proceed.
- Shield runs before persistence & quota checks to avoid counting rejected attempts.

### Quota & Metrics

- Quota: tracked per new proposal (free: 1 lifetime; paid: monthly cap resets). Section approvals, revisions, formatting do NOT consume additional quota units.
- No token-based enforcement yet (intentionally deferred); we still LOG prompt_tokens, completion_tokens for instrumentation and later pricing calibration.
- Metrics captured: retrieval_ms, embedding_ms (planner/writer phases), memory_count, fallback_mode flag (to be stored), question_hash, section_structure_hash (hash fields pending task).
- Future (deferred): anomaly detection on unusually large token bursts.

### Non-Goals (Alpha)

- No multi-user real-time collaboration or locking semantics.
- No i18n extraction (deferred; minimal English copy only).
- No semantic rerank or streaming output yet (flagged low priority backlog).
- No section deletion or re-order UI (initial order fixed after creation; future migration handles reordering if needed).

### Risks & Mitigations (Summary)

- Data migration risk (legacy proposals): idempotent command + dry run; abort if proposal already has sections.
- Circuit false positives: count only timeout/5xx/provider transport failures (exclude validation); expose counters in admin.
- Memory drift: stable ordering + hash of injected memory IDs; test asserts unchanged across runs.
- Web search fallback unreliability: capture fallback_mode metric; provide deterministic universal template to avoid blocking flow.
- Revision cap exhaustion (5) user frustration: alert early (UI shows remaining revisions) to reduce surprise.

// Edit above if product direction changes; keep lean—avoid duplicating full design docs.

## Status snapshot

- API stable: accounts/orgs/proposals/files/exports/billing/ai; JWT + Google/GitHub/Facebook OAuth; quotas + seats/extras; exports md→pdf/docx; AI plan/write/revise/format (sync or async); uploads hardened (size/MIME/magic/scan); DEBUG flows for local dev.
- SPA stable: auth/RequireOrg, proposals list/create, orgs + invites, uploads, AI flows incl. final-format, exports, paywall/upgrade, base path `/app`, minimal styling. Route-level code splitting in place for major pages. Editor includes AuthorPanel (metadata + internal notes) and SectionDiff (inline diff). Unit tests pass; jsdom guards in place.
- Security: strict CSP, Host/cookie/rate limits, OAuth state/JWKS, SSRF guards, safe external nav, webhook signature in non-DEBUG. Backups scripted; orphan scan present.
- Tests: API/Web suites green locally; RLS suite green against Postgres via task. CI covers API/Web/Docs. Linting passes (ruff, eslint-js).

## Alpha Backend Critical Path (Concise)

Focused list of backend items required for a reliable, end-to-end AI-assisted proposal flow for early alpha. (H)=High / must-have for alpha, (R)=Recommended pre-public, (M)=Monitoring/maintainability.

1. (H) Dynamic Question Generation – Planner auto-populates section questions from template banks + org metadata gap analysis; deterministic fallback when retrieval empty.

# Granterstellar — Focused Task List (updated 2025-09-09)

Legend: [ ] todo, [~] in progress, [x] done

## Alpha Critical Path (User Journey)

High‑priority backend + minimal UI tasks required for the core assisted proposal flow before broader polish.

- [x] Planner → Section Materialization (sync + async parity) & Serializer Sections Field (instantiate sections from planner blueprint; expose `sections` list; legacy `content` deprecation pending migration cmd)
- [x] Call URL Field & Immutability (model field + migration + serializer write-once guard + tests)
- [ ] Enforce 5 Revision Cap (backend enforcement + 409; central revision service)
- [ ] Dynamic Question Generation (single-run planner; staged retrieval: RAG template → RAG sample → web search ingest → universal fallback; record fallback_mode)
- [ ] Centralize Revision Service & Promotion Invariant (state=approved + locked; controlled unlock path)
- [ ] Memory Injection Upgrade (structured block; usage_count scoring; no decay)
- [ ] Prompt Safety / Injection Shield (pre-flight sanitize; high-risk reject; low-risk neutralize)
- [ ] Provider Fallback & Circuit Breaker (timeouts, retry, secondary model, cooldown)
- [ ] Metrics Extensions (tokens + timing + structure_hash + question_hash + fallback_mode flag)
- [ ] RAG Web Search Ingestion Agent (fetch remote templates/samples when RAG lacks grant-specific data; persist raw + extracted structure; queue embedding)
- [ ] RAG Progressive Prepopulation (offline script / management command to bulk ingest common grant templates & samples before alpha launch)
- [ ] Dual Asset Storage (store original PDF + extracted structured sections & headings for formatting agent reuse; link via asset id)
- [ ] Concurrent Embedding Pipeline (planner triggers background embedding tasks for newly added assets without blocking user flow)
- [ ] Org Metadata Preload Hook (inject existing org profile data into planner variable set before question gap analysis)
- [ ] Remove Quota Middleware (deduplicate enforcement; rely on permission class)
- [ ] E2E Alpha Test Flow (URL → plan (once) → Q&A → revise (≤5/section) → approve → format → export; asserts determinism & metrics)
- [ ] Documentation: ai_prompts (roles, variables, safety, metrics fields, fallback modes)
- [ ] Basic Diff UI Consumption (structured blocks; remaining revision count)

### Recently Added (Shipped This Session)

- [x] Personal Org Auto-Provision & Reuse Test (ensures single personal org reused across proposals)
- [x] Async Planner Materialization Test (`test_async_plan_materialization`) validating background job creates sections & records created keys

### Next Up (Promoted)

- [~] Enforce 5 Revision Cap
	- Introduce constant (settings override) `AI_SECTION_REVISION_CAP=5`
	- Enforce in `append_revision` (guard before save) returning error token/state
	- API revise endpoint: on cap breach return 409 `{error: 'revision_cap_reached', remaining: 0}`
	- Metrics: record cap breach event (AIMetric.success=false, reason)
	- Tests: (1) allow up to 5 revisions; (2) 6th returns 409; (3) lock/unlock does not reset count; (4) separate section independent counts
	- Serializer: include `remaining_revision_slots` per section in sections list (non-breaking additive)
	- Docs update (`proposals.md` + this Todo) after implementation

- [ ] Rudimentary Styling Baseline (layout spacing, readable typography, diff highlight minimal)

## Alpha → MVP Interim Backlog (Condensed)

Grouped tasks to lift quality from working alpha to a credible MVP; prioritize after Critical Path completion.

### AI & Retrieval

- [ ] Retrieval Caching (section/grant hash → snippet IDs TTL)
- [ ] Scheduled RAG Refresh (batch ingestion cadence + summary log)
- [ ] Re-Embed Drift Task (on embedding model version bump)
- [ ] Cleanup & TTL (purge old AIJob / contexts; archive metrics)
- [ ] Semantic Rerank (low)
- [ ] Streaming Writer (low)

### Prompt Governance & Safety

- [ ] Drift Metrics Aggregation
- [ ] Redaction Coverage Metric
- [ ] Blueprint Schema Lint (size/order guard)
- [ ] Centralized Validation Decorator

### Performance & Optimization

- [ ] Preload Critical Above-the-Fold Chunks
- [ ] Bundle Size Analysis & Budget (set target <180KB main)
- [ ] Debounce Autosaves / Limit Concurrent Fetches
- [ ] Paginate & Index Heavy Lists (proposals/orgs)
- [ ] Gzip/Br + ETag/Last-Modified for cacheable GETs
- [ ] Web Vitals Hook (debug)

### Security & Auth Hardening

- [ ] Login Scoped Throttle + Lockout
- [ ] Remove SessionAuthentication (API) except admin
- [ ] Explicit AllowAny Audit & Tests
- [ ] DRF Pagination Defaults
- [ ] Startup Env Validation (prod hard fail)

### Logging & Observability

- [ ] Request ID Middleware
- [ ] Structured JSON Logs + PII Redaction
- [ ] Timing Middleware (duration_ms)
- [ ] Upload Rejection Reason Logging + Test

### Exports & Integrity

- [ ] Size/Page Guard
- [ ] Checksum Verification Endpoint
- [ ] Export Size Metadata
- [ ] Stale Export Cleanup Task

### Billing / Usage

- [ ] Stripe Promotions Live E2E (discount reflected in /api/usage)
- [ ] Downgrade / Cancel Flow Validation

### Deployment & Containerization

- [ ] Bytecode-Only API Image (STRIP_PY)
- [ ] Multi-Stage Image (exclude docs/tests)
- [ ] Coolify Health Routes & Traefik Route Finalization
- [ ] License Banner Check (CI)

### Data & Privacy

- [ ] PII Classification Doc
- [ ] User Data Export & Delete Endpoints
- [ ] Backup Encryption Guidance

### RLS & Roles

- [ ] Explicit Role Resolver (replace is_staff inference)
- [ ] Extended Role Matrix Migration (OWNER/ADMIN/MEMBER)

### Testing Enhancements

- [ ] Planner Schema Negative Tests
- [ ] Writer JSON Rejection Test
- [ ] Reviser Missing Diff / Formatter Missing Field Tests
- [ ] Quota Denial Test
- [ ] Injection Shield Block Test
- [ ] Retrieval Fallback (no snippets) Test
- [ ] Memory Scoring Aging Test
- [ ] Security Headers (DEBUG=0)
- [ ] Throttle & Lockout Tests
- [ ] Export Checksum Stability (md/pdf/docx)
- [ ] RLS Cross-Org Negative Test

### Governance / Metrics

- [ ] Token Usage Accounting Scaffold (feed into quotas)
- [ ] Drift / Redaction Metrics Surfaced (admin)

### i18n (Deferred until post-alpha core solidifies)

- [ ] Inventory & Key Namespace Design
- [ ] Messages Store + Extraction Script
- [ ] ESLint Rule (no raw literals)

### Superadmin / Ops

- [ ] Minimal Ops Panel (quota overrides, webhook retry, usage export)

### Frontend Enhancements (Post-Alpha Styling Pass)

- [ ] Complete styling pass
- [ ] Sidebar Navigation Upgrade
- [ ] Archive & Restore UI
- [ ] Proposal Sharing UI
- [ ] Basic Dashboard (usage + recent proposals)
- [ ] Landing Page Design

## Removed Content

Status snapshots, detailed narratives, completed histories, exhaustive design checklists, and low-level execution notes have been pruned. Historical achievements and implementation details belong in `CHANGELOG.md` or dedicated docs (`docs/*`).
