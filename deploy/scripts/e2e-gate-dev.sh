#!/usr/bin/env bash
# Run infra/scripts/e2e_gate.sh against the bestmodel-dev instance.
# Host cannot reach postgres (nonprod publishes no ports). The API container
# already has DATABASE_URL on the compose network (postgres:5432/bestmodel_dev).
# This wrapper does not duplicate gate assertions: it copies the host-tree gate
# into the container (image copy may be stale) and sets BM_GATE_ATTACH=1.
# DATABASE_URL/REDIS_URL are inherited from the container env and never printed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API="${BM_DEV_API_CONTAINER:-bestmodel-dev-api-1}"
GATE_SRC="$ROOT/infra/scripts/e2e_gate.sh"

if [ ! -f "$GATE_SRC" ]; then
  echo "FAIL  missing $GATE_SRC" >&2
  exit 1
fi

if ! docker inspect -f '{{.State.Running}}' "$API" 2>/dev/null | command grep -qx true; then
  echo "FAIL  $API is not running" >&2
  exit 1
fi

docker cp "$GATE_SRC" "$API:/tmp/e2e_gate.sh"
exec docker exec \
  -e BM_GATE_ATTACH=1 \
  -e BM_GATE_WORKDIR=/app \
  -e BM_GATE_API_BASE=http://127.0.0.1:8000 \
  -w /app \
  "$API" \
  bash /tmp/e2e_gate.sh "$@"
