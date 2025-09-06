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
- `docs/ops_coolify_deployment_guide.md` (formerly install_guide) for deployment and env keys
- `README.md` for architecture and local dev
- `docs/ai_rate_limiting.md` for limiter architecture

## Access & RLS semantics

- Session GUCs via `accounts.middleware.RLSSessionMiddleware`: `app.current_user_id()`, `app.current_org_id()`, `app.current_role()`.
- Proposals READ: author; users in `shared_with`; org admins of `org_id`.
- Proposals WRITE: personal by author; org-scoped by org admin.
- OrgUser: READ self; INSERT/UPDATE/DELETE by org admin or when `(current_role='admin' and current_org_id=org_id)`.
- Organizations: INSERT (allowed; visibility via SELECT policy), DELETE by admin.
- Subscriptions: owner_user or org admin of owner_org.
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

- Core: SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL, REDIS_URL, PUBLIC_BASE_URL.
- Security: `SECURE_*` (HSTS, SSL redirect, referrer policy), `SESSION_*/CSRF_*` (secure/samesite), `CSP_SCRIPT_SRC`, `CSP_STYLE_SRC`, `CSP_CONNECT_SRC`, `CSP_ALLOW_INLINE_STYLES`.
- OAuth: GOOGLE_*, GITHUB_*, FACEBOOK_*, OAUTH_REDIRECT_URI, GOOGLE_JWKS_URL, GOOGLE_ISSUER.
- Async: EXPORTS_ASYNC, AI_ASYNC, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_ALWAYS_EAGER.
- SPA: VITE_BASE_URL, VITE_API_BASE, VITE_ROUTER_BASE, VITE_UMAMI_WEBSITE_ID, VITE_UMAMI_SRC, VITE_UI_EXPERIMENTS.
- Email: INVITE_SENDER_DOMAIN, EMAIL_* (host, port, user, password, TLS), FRONTEND_INVITE_URL_BASE.
- Billing: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_PRO_MONTHLY, PRICE_PRO_YEARLY, PRICE_ENTERPRISE_MONTHLY, PRICE_BUNDLE_1/10/25.
- Uploads/OCR: FILE_UPLOAD_MAX_BYTES, FILE_UPLOAD_MAX_MEMORY_SIZE, TEXT_EXTRACTION_MAX_BYTES, ALLOWED_UPLOAD_EXTENSIONS, OCR_IMAGE, OCR_PDF, optional VIRUSSCAN_*.
- Quotas: QUOTA_FREE_ACTIVE_CAP, QUOTA_PRO_MONTHLY_CAP, QUOTA_PRO_PER_SEAT, QUOTA_ENTERPRISE_MONTHLY_CAP.
- AI provider: AI_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY.
- AI limits: AI_RATE_PER_MIN_FREE, AI_RATE_PER_MIN_PRO, AI_RATE_PER_MIN_ENTERPRISE, AI_ENFORCE_RATE_LIMIT_DEBUG, AI_TEST_OPEN.
- Orgs/Invites: ORG_INVITE_TTL_DAYS, ORG_INVITES_PER_HOUR, APP_HOSTS.
