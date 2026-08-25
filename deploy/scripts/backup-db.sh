#!/usr/bin/env bash
# Nightly logical backup of the production database.
# Cron: 10 4 * * * /srv/bestmodel/deploy/scripts/backup-db.sh >> /srv/bestmodel/backups/backup.log 2>&1
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$HERE/../docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-$HERE/../../backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/bestmodel-$STAMP.sql.gz"

echo "[$(date -u +%FT%TZ)] dumping to $TARGET"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-bestmodel}" -d "${POSTGRES_DB:-bestmodel}" \
  | gzip >"$TARGET"

# keep the last N days of backups
find "$BACKUP_DIR" -name "bestmodel-*.sql.gz" -mtime +"$KEEP_DAYS" -delete
echo "[$(date -u +%FT%TZ)] done ($(du -h "$TARGET" | cut -f1))"
