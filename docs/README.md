[[AI_CONFIG]]
FILE_TYPE: 'INDEX_OF_DOCS'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Provide an index of documentation files', 'Distinguish active vs. archived docs', 'Guide developers to relevant documentation']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

# Documentation index

Active docs

- Install & deployment: `docs/ops_coolify_deployment_guide.md` (acts as install_guide)
- Full app overview + local dev: `README.md`
- Contributor/agent guide: `.github/copilot-instructions.md`
- Design rules (current policy): `docs/design_system.md`
- UI selectors (for future styling; reference only): `docs/style-docs.md` (alias) / `docs/frontend_design_bible.md` (canonical)
- Exports async/Celery: `docs/exports_async.md`
- Deterministic export contract: `docs/deterministic_exports.md`
- AI rate limiting & gating: `docs/ai_rate_limiting.md`
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

Precedence & consistency

- Documentation precedence chain (highest → lowest): `.github/copilot-instructions.md` → `Todo.md` → source code (runtime truth) → other docs. When a conflict exists, update lower-precedence docs to match higher-precedence intent.
- The selectors alias file `style-docs.md` exists only to prevent link rot; always edit `frontend_design_bible.md`.

Notes

- Prefer the active docs above; archived files may be outdated.
- Front-end styling is deferred until the back-end is complete. Use `docs/style-docs.md` to locate stable selectors when implementing styles later.
- Upload caps: see `docs/ops_coolify_deployment_guide.md` (FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE fallback, TEXT_EXTRACTION_MAX_BYTES).
- CSP and security headers: see `docs/security_hardening.md`.
- Stripe/webhooks and quotas: see `docs/ops_coolify_deployment_guide.md` and `README.md` for quick pointers.
	- For local testing, see README “Stripe testing (local)” on using Stripe CLI and setting STRIPE_WEBHOOK_SECRET.

Docs maintenance

- You can sanity-check links with `scripts/linkcheck.py` from the repo root (Python 3 required).
