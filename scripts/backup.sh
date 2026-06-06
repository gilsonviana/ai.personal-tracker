#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
KEEP_DAYS="${FINSIGHT_BACKUP_KEEP_DAYS:-30}"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
BACKUP_FILE="${BACKUP_DIR}/finsight_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    pg_dump -U finsight finsight | gzip > "$BACKUP_FILE"

SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
echo "[$(date)] Saved: $BACKUP_FILE ($SIZE)"

# Rotate: delete backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "finsight_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
echo "[$(date)] Rotated backups older than ${KEEP_DAYS} days."
