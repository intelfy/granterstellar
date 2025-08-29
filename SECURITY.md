# Production Hardening Notes (Repo-only)

- Docker images exclude markdown documentation, tests, and source maps via `.dockerignore`.
- SPA build disables source maps and uses hashed filenames.
- Browsable API is disabled in production (JSON renderer only).
- WhiteNoise serves fingerprinted assets with long cache.
- Keep repository private to protect design docs and implementation notes.
