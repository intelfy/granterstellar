# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning (pre-1.0 phase: rapid iteration; versions may introduce breaking changes).

## [Unreleased]

### Added

- Deterministic export pipeline (Markdown → DOCX/PDF) with normalization eliminating timestamps, volatile metadata, and ZIP nondeterminism.
- Checksum test suite (`exports/tests/test_determinism.py`) ensuring stable SHA-256 across repeated generations.
- AI rate limiting layers: plan gating, tier RPM limits (FREE/PRO/ENTERPRISE), deterministic debug single-write guard.
- AI rate limiting documentation (`docs/ai_rate_limiting.md`) and operational integration in `docs/ops_runbook.md` & `docs/security_hardening.md`.
- Security hardening expansion with AI abuse mitigation section.
- Link checker improvements: ignore build artifacts, stricter markdown spacing compliance.
- Expanded ops runbook: environment key catalog, limiter triage guidance.

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
