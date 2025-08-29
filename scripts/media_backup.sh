#!/usr/bin/env bash
# Granterstellar — Media (uploads) backup helper
# Usage:
#   bash scripts/media_backup.sh [SOURCE_DIR] [DEST_DIR]
# Defaults:
#   SOURCE_DIR=/app/media (MEDIA_ROOT in the API container)
#   DEST_DIR=/backups/media (bind mount or persistent volume)
#
# Behavior:
#   - Creates a timestamped tar.gz snapshot of SOURCE_DIR under DEST_DIR
#   - Keeps last RETAIN_DAYS snapshots (default 30)
#   - Exits non‑zero if SOURCE_DIR is missing

set -euo pipefail

SOURCE="${1:-/app/media}"
DEST="${2:-/backups/media}"
STAMP="$(date +%F_%H%M%S)"
HOSTNAME_SHORT="${HOSTNAME:-host}"
ARCHIVE="${DEST}/media_${HOSTNAME_SHORT}_${STAMP}.tar.gz"

mkdir -p "$DEST"

if [ ! -d "$SOURCE" ]; then
  echo "Source directory not found: $SOURCE" >&2
  exit 1
fi

# Create compressed snapshot; preserve perms and mtimes
tar -czf "$ARCHIVE" -C "$SOURCE" .

# Optional retention window (days)
RETAIN_DAYS="${RETAIN_DAYS:-30}"
find "$DEST" -type f -name 'media_*.tar.gz' -mtime "+$RETAIN_DAYS" -print -delete || true

echo "Backup written: $ARCHIVE"
