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

### Automated Secret Scan & Lint Hooks

- A GitHub Actions workflow (`.github/workflows/secret-scan.yml`) runs gitleaks on every push/PR to `main` and nightly; findings are advisory (build does not fail) but surface in SARIF.
- Pre-commit hooks run Ruff (lint+format), secret scan (staged only), and ESLint (scoped to `web/src`). Run `pre-commit install` after cloning to enable.
- To run all hooks manually: `pre-commit run --all-files`.

## Code Style

Python:

- Enforced by Ruff. Run `ruff format` (or rely on the pre-commit hook) before committing if you edited Python outside normal hooks.
- Quote style: single quotes are canonical (configured via `pyproject.toml [tool.ruff.format] quote-style = "single"`). Avoid mixing unless an internal single quote would force escaping (in those rare cases double quotes are acceptable for readability).
- Line length: 130 chars (see `line-length` in `pyproject.toml`). Long literals (JSON, prompts) may exceed in migrations/tests only where ignored.
- Imports: managed via Ruff (isort integration). Do not manually reorder unless resolving a failing import cycle.

JavaScript/TypeScript (web/):

- ESLint + Prettier-equivalent rules via the flat config ensure consistency. Prefer single quotes in TS/TSX except when escaping would reduce clarity.
- Keep React components pure/presentational where possible; move data fetching or side-effects to hooks/services.

Localization:

- No raw user-facing strings inline. Add keys to `locales/en.yml`, then regenerate (`node web/scripts/build_keys.mjs`). Use `t('namespace.key')` in React. Backend responses that surface to users should reference localization keys (future step) or be machine-parseable codes.

Commit hygiene around style-only churn:

- Large mechanical style changes (like the repository-wide quote normalization) must be isolated in a `chore(style): ...` commit with no behavioral changes.
- Do not mix refactors or feature logic with sweeping formatter output.

Running style/lint manually:

- Python: `ruff check .` and `ruff format --check .` (CI uses `ruff check`).
- Web: `npm run lint` (ESLint) and `npm test` (Vitest) for fast feedback.

Pre-commit:

- Hooks auto-run Ruff (lint+format), ESLint (scoped), secret scan. Install with `pre-commit install` after cloning.
