#!/usr/bin/env bash
# Restore a backup produced by backup-db.sh into the production stack.
# Usage: restore-db.sh backups/bestmodel-20260826T040000Z.sql.gz
set -euo pipefail

[ $# -eq 1 ] || { echo "usage: $0 <backup.sql.gz>"; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$HERE/../docker-compose.prod.yml"
TARGET="$1"

echo "This REPLACES the current database. Ctrl-C to abort; enter to continue."
read -r

gunzip -c "$TARGET" | docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "${POSTGRES_USER:-bestmodel}" -d "${POSTGRES_DB:-bestmodel}"

echo "restore complete — restart services to drop pooled connections:"
echo "  docker compose -f $COMPOSE_FILE restart api worker"
