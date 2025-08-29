# Security Policy

Thank you for helping keep Granterstellar and its users safe.

## Supported versions

This repository is under active MVP development. We accept reports for the `main` branch and the latest deployed version.

## Reporting a vulnerability

- Please do not open public GitHub issues for potential security problems.
- Use GitHub Security Advisories for this repository (Security > Advisories > Report a vulnerability), which creates a private workspace with maintainers.
- If that is not possible, contact us using the security contact listed on the website footer and include:
  - A description of the issue and potential impact
  - Steps to reproduce (PoC)
  - Affected component(s) and version/commit hash

We will acknowledge receipt within 3 business days and keep you informed of remediation progress. Please allow us time to remediate before public disclosure.

## Best practices we follow

- Secrets only via environment variables (managed in Coolify), never in code or images
- Django hardened defaults (HSTS/SSL/cookies), CORS allowlist, CSRF trusted origins
- Principle of least privilege for database users and RLS for tenant isolation
- CI secret scanning (Gitleaks) and pre-commit hooks to prevent accidental leaks

If you find areas to improve our posture (headers, policies, configs), suggestions are welcome via a private advisory.
