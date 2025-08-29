# Documentation index

Active docs

- Install & deployment: `docs/install_guide.md`
- Full app overview + local dev: `README.md`
- Contributor/agent guide: `.github/copilot-instructions.md`
- Design rules (current policy): `docs/design_system.md`
- Exports async/Celery: `docs/exports_async.md`
- Proposals model/endpoints and autosave: `docs/proposals.md`
- Postgres RLS policies and least-privileged DB user: `docs/rls_postgres.md`
- Security hardening notes: `docs/security_hardening.md`
- Ops runbook: `docs/ops_runbook.md`

Archived (historical context)

- `docs/archive/technical_spec_archived.md` — long-form specification
- `docs/archive/vision.md` — early product vision notes
- `docs/archive/agent_flow.md` — legacy Planner/Writer/Formatter flow
- `docs/archive/ui_overhaul_checklist.md` — prior UI redesign checklist

Notes

- Prefer the active docs above; archived files may be outdated.
- Upload caps: see `docs/install_guide.md` (FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE fallback, TEXT_EXTRACTION_MAX_BYTES).
- CSP and security headers: see `docs/security_hardening.md`.
- Stripe/webhooks and quotas: see `docs/install_guide.md` and `README.md` for quick pointers.

Docs maintenance

- You can sanity-check links with `scripts/linkcheck.py` from the repo root (Python 3 required).
