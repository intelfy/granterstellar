# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (pre-1.0 phase: rapid iteration; versions may introduce breaking changes).

## [Unreleased]

### Added

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

### Changed

- README cleanup: removed duplicate AI bullet, normalized indentation (tabs → spaces) for markdown lint compliance.
- Consolidated security documentation references; clarified CSP env-driven allow-list approach.

### Fixed

- AI async UnboundLocalError in view before job persistence; improved stability for deterministic test path.
- PDF & DOCX nondeterministic fields (timestamps, IDs, entry ordering) now neutralized producing reproducible binaries.
- Markdown lint violations in operational and security docs (heading/list spacing, trailing newline).

### Technical

- Added normalization utilities inside `api/exports/utils.py` (PDF metadata scrub, DOCX canonical zip ordering, fixed file timestamps).
- Added rate limiting helper in `api/ai/views.py` with response headers exposing remaining quota.

### Documentation

- New deterministic exports spec (`docs/deterministic_exports.md`).
- Updated `docs/ops_runbook.md` with AI rate limiting & env keys.
- Updated `docs/security_hardening.md` for layered AI abuse mitigation.

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
