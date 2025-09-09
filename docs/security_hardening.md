[[AI_CONFIG]]
FILE_TYPE: 'SECURITY_HARDENING_BIBLE'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Collect security best practices', 'Guide secure deployment and configuration', 'Ensure robust RLS and access controls']
PRIORITY: 'CRITICAL'
[[/AI_CONFIG]]

# Security hardening notes

This doc collects pragmatic, repo-specific hardening tips for production.

- Prefer local vendoring of client-side libraries (no third-party CDNs) to keep CSP strict.
- SPA production build ships without source maps and with hashed filenames; console/debugger strings are stripped by Vite config.
- Landing server does not trust Host header; serve only known hosts and set strict CSP/security headers.
- Static GET/HEAD rate limiting on landing endpoints to reduce abuse.
- Upload safety: MEDIA_ROOT containment and MIME/magic signature validation; optional virus-scan hook with timeout and fail-closed behavior.
- Served files have signature checks; avoid following symlinks out of MEDIA_ROOT.
- SPA safe external navigation helper enforces https + allow-list; test-mode opens unconditionally for unit tests.
- Optional backend obfuscation: API image supports `STRIP_PY=1` to compile to optimized .pyc and drop .py sources.
- CSP allow-lists are environment-driven: `CSP_SCRIPT_SRC`, `CSP_STYLE_SRC`, `CSP_CONNECT_SRC` (comma-separated; 'self' auto-added). Avoid inline styles; `CSP_ALLOW_INLINE_STYLES=1` escape hatch only when necessary.
- AI rate limiting provides defense-in-depth against automated abuse (see section below).

See also:

- `.github/SECURITY.md` for the disclosure policy
- `docs/ops_coolify_deployment_guide.md` for deployment and env keys
- `README.md` for architecture and local dev
- `docs/ai_rate_limiting.md` for limiter architecture

## Access & RLS semantics

- Session GUCs via `accounts.middleware.RLSSessionMiddleware`: `app.current_user_id()`, `app.current_org_id()`, `app.current_role()`.
- Proposals READ: author; users in `shared_with`; org admins of `org_id`.
- Proposals WRITE: personal by author; org-scoped by org admin.
- OrgUser: READ self; INSERT/UPDATE/DELETE by org admin or when `(current_role='admin' and current_org_id=org_id)`.
- Organizations: INSERT (allowed; visibility via SELECT policy), DELETE by admin.
- Subscriptions: owner_user or org admin of owner_org for write; read also allowed for any org member via `subscriptions_read_members` (SELECT-only) policy to surface accurate usage limits without granting modification rights.
- FORCE RLS enabled on orgs_organization, orgs_orguser, proposals_proposal, billing_subscription.
- Policies in `db_policies/migrations/0001_rls.py` (+ subsequent migrations 0002–0009). Postgres-only tests in `db_policies/tests/*` (skipped on SQLite).

## Global Security & hardening

- Strict CSP/security headers (env allow-lists). No source maps in prod; strip console/debugger. Images exclude docs/tests/maps.
- Landing server: known hosts only; static GET/HEAD rate limiting.
- Upload safety: MEDIA_ROOT containment; MIME/magic validation; served file signature checks; optional virus-scan hook.
- SPA `safeOpenExternal` enforces https + allow-list; test-mode opens unconditionally.
- Optional: API image build arg `STRIP_PY=1` compiles to .pyc and drops sources.

## AI rate limiting & abuse mitigation

Layered controls protect provider quotas and prevent brute-force misuse:

- Plan gating: Certain AI endpoints require paid plan (Pro / Enterprise) – prevents free-tier model abuse.
- Tier RPM limits: Per-minute request ceilings set via environment variables (see below).
- Deterministic debug guard: In DEBUG, optional single-write limiter (enforce via `AI_ENFORCE_RATE_LIMIT_DEBUG=1`) ensures reproducible tests and shields from accidental loops.
- Cache-backed counters: Lightweight in-process + cache keys; failure should fail-open (prefer availability) but logs warning.

Security considerations:

- Keep RPM values conservative while usage patterns stabilize; adjust upward gradually.
- Combine with authentication (JWT + org scoping) to avoid anonymous amplification.
- Monitor 429 rates; sudden spikes could indicate scripted abuse or compromised token.

Environment variables:

- `AI_RATE_PER_MIN_FREE`
- `AI_RATE_PER_MIN_PRO`
- `AI_RATE_PER_MIN_ENTERPRISE`
- `AI_ENFORCE_RATE_LIMIT_DEBUG` (0/1)
- `AI_TEST_OPEN` (relaxed gating in test scenarios)

Reference: `docs/ai_rate_limiting.md` (design), `docs/ops_runbook.md` (operational triage).

## CI & release invariants

- web/dist: no source maps; no console/debugger strings.
- Images: exclude docs/tests/maps; API supports `STRIP_PY=1`.
- Host header: reject untrusted; CSP allow-lists minimal and env-driven.

## Environment keys (high-impact)

This list duplicated the deployment guide and is now canonicalized.

Authoritative matrix: `docs/ops_coolify_deployment_guide.md` (see the section "Environment Variable Matrix"). That file is the single source of truth for:

- Variable purpose, type, required/conditional flags.
- Defaults and operational notes.
- Future additions (add there first; then reference here if security relevant).

Security-relevant subsets to monitor (quick reference only):

- Core secrets & boundaries: `SECRET_KEY`, `JWT_SIGNING_KEY`, `ALLOWED_HOSTS`, `PUBLIC_BASE_URL`.
- Transport/cookies: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `SESSION_COOKIE_SAMESITE`, `CSRF_COOKIE_SAMESITE`.
- CSP: `CSP_SCRIPT_SRC`, `CSP_STYLE_SRC`, `CSP_CONNECT_SRC`, `CSP_ALLOW_INLINE_STYLES`.
- AI & quota gating: `AI_RATE_PER_MIN_*`, `AI_DAILY_REQUEST_CAP_*`, `AI_MONTHLY_TOKENS_CAP_*`, `AI_ENFORCE_RATE_LIMIT_DEBUG`, `AI_DETERMINISTIC_SAMPLING`.
- Upload & scanning: `FILE_UPLOAD_MAX_BYTES`, `TEXT_EXTRACTION_MAX_BYTES`, `ALLOWED_UPLOAD_EXTENSIONS`, `VIRUSSCAN_CMD`, `VIRUSSCAN_TIMEOUT_SECONDS`.
- Billing integrity: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PRICE_*`.
- Async execution trust surface: `EXPORTS_ASYNC`, `AI_ASYNC`, `CELERY_*`, `REDIS_URL`.

If a variable affects security posture and is added to the matrix, add a bullet above (do not recreate the full matrix here).
