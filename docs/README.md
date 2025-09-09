# Documentation index

[[AI_CONFIG]]
FILE_TYPE: 'INDEX_OF_DOCS'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Provide an index of documentation files', 'Distinguish active vs. archived docs', 'Guide developers to relevant documentation']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

Active docs

- Install & deployment: `docs/ops_coolify_deployment_guide.md`
- Full app overview + local dev: `README.md`
- Contributor/agent guide: `.github/copilot-instructions.md`
- Design rules (current policy): `docs/design_system.md`
- UI selectors (for future styling; reference only): `docs/frontend_design_bible.md` (canonical; alias archived)
- Exports architecture (async + deterministic): `docs/exports.md`
- AI rate limiting & gating: `docs/ai_rate_limiting.md`
- RAG ingestion & retrieval (phase 1): `docs/rag_ingestion.md`
- Prompt contracts & rendering: `docs/prompt_contracts.md`
- Proposals model/endpoints and autosave: `docs/proposals.md`
- Postgres RLS policies and least-privileged DB user: `docs/rls_postgres.md`
	- Matrix test coverage file: `db_policies/tests/test_rls_matrix.py` (CRUD + negative membership insert focus)
- Security hardening notes: `docs/security_hardening.md`
- Ops runbook: `docs/ops_runbook.md`

Archived (historical context)

- `docs/archive/technical_spec_archived.md` — long-form specification
- `docs/archive/vision.md` — early product vision notes
- `docs/archive/agent_flow.md` — legacy Planner/Writer/Formatter flow
- `docs/archive/ui_overhaul_checklist.md` — prior UI redesign checklist

Legacy artifacts (contextual summary)

- Exports docs were previously split (`exports_async.md`, `deterministic_exports.md`); both consolidated into active `exports.md` for a single source of truth (async + deterministic normalization + checksum rationale).
- The old installation guide (`install_guide.md`) content is fully merged into `ops_coolify_deployment_guide.md`; any lingering references should be removed (third-pass audit complete).
- Front-end selectors alias (`style-docs.md`) is archived; `frontend_design_bible.md` is canonical going forward.
- Proposals once allowed personal (non-org) ownership; model migrated to org-only with legacy personal proposals retained read-only until user/org migration is complete (documented in `proposals.md`).
- Environment variable lists that previously appeared in multiple docs (README, runbook) are now centralized—matrix lives only in the deployment guide to prevent drift.

Precedence & consistency

- Documentation precedence chain (highest → lowest): `.github/copilot-instructions.md` → `Todo.md` → source code (runtime truth) → other docs. When a conflict exists, update lower-precedence docs to match higher-precedence intent.
- The former selectors alias `style-docs.md` has been archived; edit `frontend_design_bible.md`.

Notes

- Prefer the active docs above; archived files may be outdated.
- Front-end styling is deferred until the back-end is complete. Use `docs/frontend_design_bible.md` to locate stable selectors when implementing styles later.
- Upload caps: see `docs/ops_coolify_deployment_guide.md` (FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE fallback, TEXT_EXTRACTION_MAX_BYTES).
- CSP and security headers: see `docs/security_hardening.md`.
- Environment variable matrix is authoritative only in `docs/ops_coolify_deployment_guide.md`; other docs now reference it instead of duplicating.
- Stripe/webhooks and quotas: see `docs/ops_coolify_deployment_guide.md` and `README.md` for quick pointers.
	- For local testing, see README “Stripe testing (local)” on using Stripe CLI and setting STRIPE_WEBHOOK_SECRET.

Docs maintenance

- You can sanity-check links with `scripts/linkcheck.py` from the repo root (Python 3 required).
