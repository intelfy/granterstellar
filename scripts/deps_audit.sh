#!/usr/bin/env bash
set -euo pipefail

echo "[deps-audit] Python: pip-audit (prod + dev)"
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -f json -o pip-audit-report.json || true
else
  echo "pip-audit not installed (skip)" >&2
fi

echo "[deps-audit] Node: npm audit (prod JSON)"
if command -v npm >/dev/null 2>&1; then
  (cd web && npm audit --omit=dev --json > npm-audit-prod.json || true)
else
  echo "npm not installed (skip)" >&2
fi

echo "[deps-audit] Node: npm audit (full JSON)"
if command -v npm >/dev/null 2>&1; then
  (cd web && npm audit --json > npm-audit-full.json || true)
fi

echo "[deps-audit] Generate CycloneDX SBOM (if tool present)"
if command -v cyclonedx-py >/dev/null 2>&1; then
  cyclonedx-py -o sbom-python.json || true
fi
if command -v cyclonedx-npm >/dev/null 2>&1; then
  (cd web && cyclonedx-npm -o sbom-node.json || true)
fi

echo "[deps-audit] Summaries (jq)"
if command -v jq >/dev/null 2>&1; then
  if [ -f pip-audit-report.json ]; then
    echo "python pip-audit high=$(jq '[.[] | .vulns[]? | select((.severity? // .advisory.severity?) | ascii_upcase=="HIGH")] | length' pip-audit-report.json) critical=$(jq '[.[] | .vulns[]? | select((.severity? // .advisory.severity?) | ascii_upcase=="CRITICAL")] | length' pip-audit-report.json)";
  fi
  if [ -f web/npm-audit-full.json ]; then
    echo "node full high=$(jq '.vulnerabilities.high? // ([.advisories[]? | select(.severity=="high")] | length)' web/npm-audit-full.json) critical=$(jq '.vulnerabilities.critical? // ([.advisories[]? | select(.severity=="critical")] | length)' web/npm-audit-full.json)";
  fi
  if [ -f web/npm-audit-prod.json ]; then
    echo "node prod high=$(jq '.vulnerabilities.high? // ([.advisories[]? | select(.severity=="high")] | length)' web/npm-audit-prod.json) critical=$(jq '.vulnerabilities.critical? // ([.advisories[]? | select(.severity=="critical")] | length)' web/npm-audit-prod.json)";
  fi
else
  echo "jq not installed (skip summaries)" >&2
fi

echo "[deps-audit] Done"