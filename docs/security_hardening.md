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

See also:
- `.github/SECURITY.md` for the disclosure policy
- `docs/install_guide.md` for deployment and env keys
- `README.md` for architecture and local dev
