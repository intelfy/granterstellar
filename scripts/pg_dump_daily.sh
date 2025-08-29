#!/usr/bin/env sh
set -euo pipefail

# Simple daily PostgreSQL dump into /backups (mounted persistent volume)
# Requires: DATABASE_URL or PG* env vars available to psql/pg_dump

BACKUP_DIR=${BACKUP_DIR:-/backups}
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)

if [ -n "${DATABASE_URL:-}" ]; then
  URI="$DATABASE_URL"
else
  echo "ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

OUT="$BACKUP_DIR/db-$STAMP.sql.gz"
echo "[pg_dump_daily] Writing $OUT"
pg_dump "$URI" | gzip -c > "$OUT"
echo "[pg_dump_daily] Done"
