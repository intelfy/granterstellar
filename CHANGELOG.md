# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (pre-1.0 phase: rapid iteration; versions may introduce breaking changes).

## [Unreleased]

### Localization (UI Keys Insertion Workflow)

All user-visible UI text must come from `locales/en.yml` and be accessed via the generated translator.

Workflow:

1. Add/modify keys in `locales/en.yml` (nest under `ui.*` namespaces; keep logical grouping e.g. `ui.dashboard.*`, `ui.billing.*`).
2. Regenerate keys: `node scripts/build_keys.mjs` (writes `web/src/keys.generated.ts`). Never edit the generated file manually.
3. Use in code: `import { t } from '../keys.generated'` then `t('ui.namespace.key', { optional: 'params' })`.
4. Replace raw user-facing literals immediately; allow TEMP raw strings only if marked with `// TODO i18n` (should not reach commit without conversion).
5. For interpolations, ensure placeholders exist in YAML: `section_counter: "Section {current} of {total}"` then call with params object.
6. Commit both the YAML and regenerated `keys.generated.ts` together.
7. Update tests: replace literal expectations with either the translated string or (preferably) the key-driven output if stable.

Rules / Guardrails:

- No direct `KEYS` map access inside components (prevents test race conditions); rely on `t()` which safely falls back to the key string.
- Do not remove or rename a key without searching usages; rename in a single commit to avoid stale references.
- Missing key at runtime returns the key string itself—treat as a defect and add the YAML entry.
- Keep key names descriptive (avoid cryptic abbreviations).
- Keep interpolation placeholder names lowercase and meaningful.

Planned CI (future):

- Lint rule forbidding new raw English literals in `web/src` except test files.
- Deterministic check ensuring `keys.generated.ts` matches `locales/en.yml`.

### Added

- Revision cap enforcement refinements:
	- DRY utility `get_revision_cap()` (`proposals/utils.py`) centralizing `PROPOSAL_SECTION_REVISION_CAP` retrieval (default 5, sanitized to positive int).
	- AI metrics reason constant `REVISION_CAP_REASON` (`ai/constants.py`) replacing ad-hoc literal strings for failure instrumentation consistency.
	- Enhanced revise 409 response payload now includes `revision_count` and `revision_cap` alongside existing `error` and `remaining_revision_slots`, enabling clients to display precise usage and limits.
	- Documentation update in `docs/proposals.md` with explicit 409 schema snippet; related tests (`ai/tests/test_revision_cap.py`) updated to assert new fields.
	- All AI + core test suites passing post-refactor (no behavior change beyond richer payload & metric normalization).

- Deterministic export pipeline (Markdown → DOCX/PDF) with normalization eliminating timestamps, volatile metadata, and ZIP nondeterminism.
- Checksum test suite (`exports/tests/test_determinism.py`) ensuring stable SHA-256 across repeated generations.
- AI rate limiting layers: plan gating, tier RPM limits (FREE/PRO/ENTERPRISE), deterministic debug single-write guard.
- RLS policy `subscriptions_read_members` permitting org members SELECT visibility of their org subscription (write still restricted to admin/owner) enabling accurate usage/tier display.
- AI rate limiting documentation (`docs/ai_rate_limiting.md`) and operational integration in `docs/ops_runbook.md` & `docs/security_hardening.md`.
- Security hardening expansion with AI abuse mitigation section.
- Link checker improvements: ignore build artifacts, stricter markdown spacing compliance.
- Expanded ops runbook: environment key catalog, limiter triage guidance.
- Deterministic AI provider flag & request override (`deterministic` boolean) for write/revise/format endpoints (default via `AI_DETERMINISTIC_SAMPLING`).
- Enforcement of org-only proposals (legacy personal proposals backfilled & deprecated) via migrations `0002_require_org_on_proposal`, `0003_merge_enforce_org`, `0003_require_org_on_proposal`.
- Granular proposal RLS: separate INSERT/UPDATE/DELETE policies requiring org admin role + `app.current_role()='admin'` (migrations 0010–0013) and member read-only subscription visibility.
- Tightened RLS policies replacing broad FOR ALL proposal write with granular admin-gated set; member subscription read-only policy.
- Documentation updates (`docs/rls_postgres.md`, `docs/security_hardening.md`) reflecting org-only proposals & subscription visibility.
- Backfill logic migrates legacy personal proposals into per-user synthetic orgs before NOT NULL enforcement.
- Section promotion API endpoint: `POST /api/sections/{id}/promote` (locks section, copies draft_content → content) and unlock via `DELETE /api/sections/{id}/promote`.
- AIMetric instrumentation for `promote` events (type `promote`) recording proposal & section context for lifecycle analytics.
- Prompt blueprint system: optional `blueprint_schema` + `blueprint_instructions` appended only for formatter role, enabling structured output guidance.
- Deterministic multi-category redaction (EMAIL, NUMBER, PHONE, ID_CODE, SIMPLE_NAME, ADDRESS_LINE) with hashed tokens `[CATEGORY_<hash>]` and persisted `redaction_map` for audit.
- Template drift detection via stored `template_sha256` in `AIJobContext` and `detect_template_drift` helper.
- Structured diff revision pipeline: semantic paragraph diff engine (`ai/diff_engine.py`) producing `change_ratio` and ordered `blocks` (types: `equal|replace|insert|delete`, optional `similarity`).
- Dual-schema reviser output validator accepting new structured blocks or legacy `added`/`removed` arrays for backward compatibility (`validate_reviser_output`).
- Revision logging with size guards: stores normalized diff metadata & caps (50 revisions, 25 blocks, per-block and text truncation) in `ProposalSection.append_revision`.
- Provider revise contract stabilization: `Gpt5Provider` & `GeminiProvider` now deterministically emit validated structured diffs (no placeholder fabrication) enabling reliable tests.
- No-op migration marker (`proposals/migrations/0007_structured_diff_logging_noop.py`) documenting adoption without schema changes.
- Documentation: Structured Diff section added to `docs/prompt_contracts.md` detailing schema, truncation, compatibility, and future roadmap.

### Changed

- Prompt contracts doc expanded with blueprint injection, deterministic redaction taxonomy, and drift detection workflow.
- Reviser task now supplies real semantic diff output rather than stub arrays; legacy consumers remain supported during transition.
- README cleanup: removed duplicate AI bullet, normalized indentation (tabs → spaces) for markdown lint compliance.
- Consolidated security documentation references; clarified CSP env-driven allow-list approach.

### Fixed

- AI async UnboundLocalError in view before job persistence; improved stability for deterministic test path.
- PDF & DOCX nondeterministic fields (timestamps, IDs, entry ordering) now neutralized producing reproducible binaries.
- Markdown lint violations in operational and security docs (heading/list spacing, trailing newline).
- Provider revise methods indentation & scope errors (F821/F706) resolved; eliminated undefined name & return-outside-function issues.

### Technical

- Added normalization utilities inside `api/exports/utils.py` (PDF metadata scrub, DOCX canonical zip ordering, fixed file timestamps).
- Added rate limiting helper in `api/ai/views.py` with response headers exposing remaining quota.

### Documentation

- New deterministic exports spec (now unified in `docs/exports.md`, merging former `exports_async.md` + `deterministic_exports.md`).
- Updated `docs/ops_runbook.md` with AI rate limiting & env keys.
- Updated `docs/security_hardening.md` for layered AI abuse mitigation.
- Consolidated exports docs; archived legacy files under `docs/archive/` to preserve historical context and avoid link rot.
- Broad documentation cleanup: removed obsolete `install_guide` references, clarified org-only proposals model, trimmed duplicated env key lists (now referencing single authoritative matrix), removed deprecated alias parentheticals.

---
Template for future releases:

## [x.y.z] - YYYY-MM-DD (Template)

### Added (Template)

-

### Changed (Template)

-

### Fixed (Template)

-

### Removed (Template)

-

### Security (Template)

-

---

## Archive (Task History up to 2025-09-09)

This archive captures the detailed status snapshot, recently completed items, and auxiliary planning/backlog material that was removed from `Todo.md` during the alpha focus slim‑down on 2025-09-09. It is retained here for historical traceability. New work should NOT be appended to this archive section; continue using the streamlined `Todo.md` and regular changelog entries instead.

### Status Snapshot (Pre-Slimdown)

- API stable: accounts/orgs/proposals/files/exports/billing/ai; JWT + Google/GitHub/Facebook OAuth; quotas + seats/extras; exports md→pdf/docx; AI plan/write/revise/format (sync or async); uploads hardened (size/MIME/magic/scan); DEBUG flows for local dev.
- SPA stable: auth/RequireOrg, proposals list/create, orgs + invites, uploads, AI flows incl. final-format, exports, paywall/upgrade, base path `/app`, minimal styling. Route-level code splitting for major pages. Editor includes AuthorPanel (metadata + internal notes) and SectionDiff (inline diff). Unit tests pass.
- Security: strict CSP, Host/cookie/rate limits, OAuth state/JWKS, SSRF guards, safe external nav, webhook signature (non-DEBUG). Backups scripted; orphan scan present.
- Tests: API/Web suites green; RLS suite green against Postgres via task. Linters (ruff, eslint) passing.

### Recently Completed (2025-09-09)

- Structured diff revision pipeline end-to-end: semantic diff engine (`ai/diff_engine.py`) producing `change_ratio` & ordered block list (`equal|replace|insert|delete`, optional similarity) consumed by provider revise methods.
- Dual-schema validator (`validate_reviser_output`) accepts structured blocks or legacy arrays for backward compatibility.
- Provider revise contract stabilization: `Gpt5Provider` & `GeminiProvider` emit validated structured diffs (removed placeholder fabrication / indentation scope errors).
- Revision logging enhancements: `ProposalSection.append_revision` caps (50 revisions, 25 blocks) with truncation safeguards.
- Documentation: `docs/prompt_contracts.md` updated (Structured Diff section); CHANGELOG updated with structured diff feature bullets.

### Recently Completed (2025-09-08)

- Formatter blueprint injection (conditional roles).
- Template drift detection (`template_sha256`) + checksum recomputation on save.
- Deterministic redaction taxonomy with persisted `redaction_map`.

### Prompt / AI Governance (Follow-Ups Backlog at Time of Archive)

- Drift metrics aggregation & admin report.
- Redaction coverage metric.
- Negative control drift test.
- Admin UI: original vs redacted prompt snapshot.
- Blueprint schema lint (size/order guard) in CI.
- Redaction map diff tool (taxonomy expansion).
- Centralized validation wrapper/decorator.
- Auto-repair trivial planner issues.

### AI Memory (State at Archive)

- Implemented `AIMemory` with suggestions endpoint; dedup on `(created_by, org_id, key_hash, value_hash)`.
- Prompt integration (write: `_memory_context` block; revise: appended memory context) using underscore key to avoid persistence loops.
- Frontend: `useAIMemorySuggestions` + chips in AuthorPanel; tests green.
- Follow-ups: configurable token truncation, per-key weighting, structured memory context contract evolution.

### Performance & Optimization Plan (Pre-Slimdown)

Web Build / Bundling:

- Route-level code splitting implemented; further preload & bundle budget tasks pending.
- Baseline (2025-09-01 local): total gzipped JS ≈ 59.8 KB; largest chunk vendor-react ≈ 43.7 KB.

Runtime Client:

- Planned: debounce autosaves/search, in-memory cache (SWR style), list virtualization, navigation cleanup.

API Efficiency:

- Planned: ensure pagination + indexes, short-lived Redis caches, batch bootstrap endpoint.

Infra / Delivery:

- Planned: gzip/br + immutable hashed assets, optional CDN.

Guardrails & SLOs:

- Targets (proposed): p95 TTI < 2.5s, main bundle < 180KB gzip, TBT < 200ms.

### Security / Auth Backlog (Archived Detail)

- Login scoped throttle & lockout; remove SessionAuthentication (except admin); explicit AllowAny audits; DRF pagination defaults; startup env fail-fast; structured logging with request IDs; PII redaction in logs; throttled upload logging.

### Exports & Integrity Backlog

- Size/page guard, checksum verification endpoint, export size metadata, stale job cleanup.

### RLS & Roles Backlog

- Replace staff inference with explicit role resolver; extended role matrix migration; negative cross-org leakage tests.

### Data & Privacy Backlog

- PII classification doc; user data export & deletion; backup encryption guidance; redaction in structured logs.

### Deployment / Containerization Backlog

- Bytecode-only build (`STRIP_PY`); multi-stage image excluding docs/tests; license banner CI check; Coolify health route validation.

### Testing Enhancements (Archived List)

- Planner schema negative, writer JSON rejection, reviser diff validation, formatter field enforcement, quota denial, injection shield blocking, retrieval fallback, memory scoring aging, security headers (DEBUG=0), throttling & lockout, export checksum stability, RLS negative cross-org.

### i18n Readiness Plan (Deferred at Archive)

Phases: inventory script, key namespace design, minimal `t()` runtime, messages store, extraction tooling, interpolation, template extraction, backend `USE_I18N`, ESLint rule (no raw literals), CI guard, progress metric, accessibility scans, docs (`docs/i18n.md`), unused key cleanup, future locale switcher.

### IP Protection / Build Hardening Items (Archived)

- No source maps in prod, strip comments except license banners, drop console/debugger, exclude non-runtime artifacts, optional `.py` stripping, multi-stage Docker, distinct SECRET_KEY/JWT keys.

### Environment Doctor (Completed Prior to Archive)

- `manage.py env_doctor --strict` with exit codes 0/1/2; CI integration; validates secrets, host safety, conditional groups (Stripe/OAuth/Redis/AI), warns identical JWT/SECRET_KEY.

### Superadmin Dashboard (Planned)

- Quota overrides, webhook retry/sync, usage export, feature toggles, bans, model switches (IsSuperUser gated).

### Frontend Future (High-Level at Archive)

- Sidebar navigation, proposal archive/restore, sharing, dashboard (usage + recent), enhanced dialogs/modals, design language ("living typewriter"), multi-step survey UI.

### Miscellaneous Backlog (Archived)

- Dependency & supply chain: pip-tools constraints, npm lockfile CI, dependency triage doc, SBOM generation (completed), weekly Dependabot (completed).
- Structured logging: JSON logs with duration, redaction, request_id.
- Operations metrics: request latency, AI invocation duration, Celery success/failure counts.
- Maintainability refactors: split `settings.py`, centralize file security helpers, extract billing webhook service functions.

### Rationale for Slimdown

The above details provided valuable planning fidelity but introduced cognitive overhead. They are preserved verbatim here to avoid knowledge loss while enabling a lean, execution-focused `Todo.md` centered on the Alpha Critical Path and a concise Alpha→MVP backlog.
