#!/usr/bin/env bash
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks not found. Install: https://github.com/gitleaks/gitleaks/releases" >&2
  exit 2
fi

# Gate ONLY on staged changes (fast, low-noise). Optional full scan is advisory.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[secret-scan] Scanning STAGED changes (gating)..."
  gitleaks protect --staged --no-banner --config .gitleaks.toml
  echo "[secret-scan] Staged scan passed."
  if [ "${FULL_HISTORY_SCAN:-0}" = "1" ]; then
    echo "[secret-scan] Running FULL HISTORY scan (advisory, won't fail build)..."
    set +e
    gitleaks detect --no-banner --config .gitleaks.toml || echo "[secret-scan] Advisory full scan reported findings (see above)."
    set -e
  fi
else
  echo "[secret-scan] Not a git repository; scanning working directory (gating)..."
  gitleaks detect --no-banner --no-git --config .gitleaks.toml
fi

echo "[secret-scan] Completed. No new secrets detected in staged content."
