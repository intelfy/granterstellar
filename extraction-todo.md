# Copy Extraction Checklist

Incrementally replace literals with keys in `locales/en.yml` using backend `t()` and frontend generated `t()`.

## Backend (Django)

- [ ] `api/accounts/`
- [ ] `api/ai/views.py`
- [ ] `api/ai/tasks.py`
- [ ] `api/ai/prompting.py`
- [ ] `api/ai/diff_engine.py` (user-facing diffs? minimal)
- [ ] `api/app/middleware.py`
- [ ] `api/app/errors.py`
- [ ] `api/app/settings.py` (public error messages only)
- [ ] `api/billing/views.py`
- [ ] `api/billing/webhooks.py`
- [ ] `api/billing/middleware.py`
- [ ] `api/files/`
- [ ] `api/exports/`
- [ ] `api/orgs/`
- [ ] `api/proposals/serializers.py`
- [ ] `api/proposals/models.py` (validation messages)
- [ ] `api/proposals/views.py` (if exists)
- [ ] `api/db_policies/` (messages if any)
- [ ] `api/templates/` (HTML templates static copy)

## Frontend (web/src)

- [ ] `web/src/index.*`
- [ ] `web/src/components/` (iterate each component)
- [ ] `web/src/routes/`
- [ ] `web/src/hooks/` (user messages, toasts)
- [ ] `web/src/utils/` (validation errors surfaced to users)
- [ ] `web/src/pages/` if present

## Shared / Root

- [ ] `README.md` (marketing copy optional)
- [ ] `index.html` (landing page copy)
- [ ] `privacy.html`
- [ ] `confirmed.html`
- [ ] `script.js`

## Extraction Steps (Per File)

1. Identify literals (sentences, button labels, alerts, headings).
2. Add key to `locales/en.yml` under appropriate namespace.
3. Backend: replace with `from app.common.keys import t` (top) and `t('scope.key', param=value)`.
4. Frontend: use imported `t` from `keys.generated.ts` after running `npm run build:keys` if new key.
5. Update tests referencing the literal; prefer asserting via `t('key')` or pattern.
6. Commit in small batches (group related domain keys).

## Pending Enhancements

- [ ] Add CI check ensuring `web/src/keys.generated.ts` matches `en.yml`.
- [ ] Add script to scan for high-probability literals (regex heuristic).
- [ ] Add logging for missing keys (single warn set) in DEBUG.
