# Contributing to Granterstellar

Welcome! This project favors concise, accurate docs and tests. Start here:

- Docs index: `docs/README.md`
- Contributor/agent guide: `.github/copilot-instructions.md`
- Install/deploy: `docs/ops_coolify_deployment_guide.md`

## Local development
- API (Django): use VS Code tasks
  - API: migrate, runserver (DEBUG), lint (ruff), tests per app
- Web (React/Vite): dev, lint
- Both: task "Dev: API + Web"

## Tests and lint
- Python: ruff for lint/format; run per-app Django tests to avoid discovery collisions
- Web: ESLint (flat config), Vitest for unit tests
- Postgres-only RLS tests: set `DATABASE_URL` and run the RLS test task

## Conventions
- No inline styles in SPA; minimal markup (see `docs/design_system.md`)
- SPA base paths: `/app` for routes, `/static/app/` for assets
- Proposal content is JSONB; prefer PATCH for autosave
- Keep CSP strict; vendor client libraries locally when possible

## Useful pointers
- RLS: `docs/rls_postgres.md`
- Exports (async + determinism unified): `docs/exports.md`
- Proposals API: `docs/proposals.md`

## Reporting security issues
- Do not open public issues. See `.github/SECURITY.md` for our policy.

## Secrets & Environment Hygiene

Never commit real secrets. All runtime credentials must come from environment variables loaded via `.env` (which is gitignored) or your deployment platform.

Before pushing:

1. Run `bash scripts/secret_scan.sh` (wraps gitleaks staged + full repo scan).
2. Run `python api/manage.py env_doctor --strict` to validate required env keys (in CI this should also run).
3. Confirm any newly added UI strings follow the localization workflow (`locales/en.yml` + regenerate keys).

If a secret leaks:

- Rotate the credential immediately in the upstream provider.
- Remove the secret from git history (filter-repo) only if compliance requires; otherwise rely on rotation.
- Document the rotation (internal log) with date/time and reason.

Local `.vscode/`, `.env*`, and other ignored files may contain secrets—keep them private. The repository includes `.gitleaks.toml` to reduce false positives; adjust allowlist sparingly.
