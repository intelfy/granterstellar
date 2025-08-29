# Contributing to Granterstellar

Welcome! This project favors concise, accurate docs and tests. Start here:

- Docs index: `docs/README.md`
- Contributor/agent guide: `.github/copilot-instructions.md`
- Install/deploy: `docs/install_guide.md`

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
- Exports async: `docs/exports_async.md`
- Proposals API: `docs/proposals.md`

## Reporting security issues
- Do not open public issues. See `.github/SECURITY.md` for our policy.
