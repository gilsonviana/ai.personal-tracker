#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <path/to/finsight_YYYYMMDD_HHMMSS.sql.gz>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "WARNING: This will DROP and recreate the 'finsight' database."
echo "Backup file: $BACKUP_FILE"
read -r -p "Type 'yes' to continue: " confirm
[[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 0; }

echo "[$(date)] Dropping existing database..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    dropdb -U finsight --if-exists finsight

echo "[$(date)] Creating fresh database..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    createdb -U finsight finsight

echo "[$(date)] Restoring from $BACKUP_FILE..."
gunzip -c "$BACKUP_FILE" | \
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    psql -U finsight finsight

echo "[$(date)] Restore complete. Run 'alembic upgrade head' if schema migrations are needed."
