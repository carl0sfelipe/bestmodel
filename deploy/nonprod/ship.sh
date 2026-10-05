#!/usr/bin/env bash
# Ship a commit to a nonprod stack (dev|stag):
#   - refuse uncommitted changes under apps/ packages/ infra/ deploy/
#   - always rebuild web-next (runner target), stamped with the commit revision
#   - rebuild api/worker only when their paths changed since the running
#     image's org.opencontainers.image.revision label (or with --all)
#   - recreate the affected services, wait for health, then run the smoke
#
#   bash deploy/nonprod/ship.sh dev
#   bash deploy/nonprod/ship.sh stag --all
set -euo pipefail

usage() {
  echo "usage: ship.sh dev|stag [--all]" >&2
  exit 2
}
ENV_NAME="${1:-}"
case "$ENV_NAME" in dev|stag) ;; *) usage ;; esac
ALL=0
[ "${2:-}" = "--all" ] && ALL=1
[ "${#}" -le 2 ] || usage

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT="bestmodel-${ENV_NAME}"
ENV_DIR="/data/bestmodel/nonprod/${ENV_NAME}"
ENV_FILE="${ENV_DIR}/compose.env"
if [ ! -s "$ENV_FILE" ]; then
  echo "missing $ENV_FILE — run: bash deploy/nonprod/init-env.sh $ENV_NAME" >&2
  exit 1
fi

cd "$REPO_ROOT"

compose() {
  docker compose -p "$PROJECT" \
    -f deploy/docker-compose.prod.yml \
    -f deploy/docker-compose.nonprod.yml \
    --env-file "$ENV_FILE" \
    "$@"
}

# Refuse to ship with uncommitted changes under the paths that feed images.
DIRTY="$(git status --porcelain -- apps packages infra deploy)"
if [ -n "$DIRTY" ]; then
  echo "refusing to ship: uncommitted changes under apps/ packages/ infra/ deploy/:" >&2
  echo "$DIRTY" >&2
  exit 1
fi

# Revision convention shared with the api/worker images (deploy/build-args.sh).
eval "$(deploy/build-args.sh)"
REV="$BESTMODEL_GIT_SHA"

WEB_PATHS="apps/web-next infra/docker/web-next.Dockerfile .dockerignore docs/agent-quickstart.md"
API_PATHS="apps/public-api apps/intake-worker packages infra/docker/api.Dockerfile"

running_rev() { # $1 = service -> revision label of its running image (or "")
  local cid img
  cid="$(compose ps -q "$1" 2>/dev/null | head -n1)"
  [ -n "$cid" ] || return 0
  img="$(docker inspect --format '{{.Image}}' "$cid")"
  docker image inspect "$img" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true
}

WEB_REV="$(running_rev web)"
API_REV="$(running_rev api)"

BUILD_API=0
if [ "$ALL" -eq 1 ] || [ -z "$API_REV" ] || ! git diff --quiet "$API_REV" HEAD -- $API_PATHS; then
  BUILD_API=1
fi

echo "ship $ENV_NAME @ $REV"
echo "web: rebuild (running: ${WEB_REV:-<none>})"
echo "api/worker: $([ "$BUILD_API" -eq 1 ] && echo rebuild || echo up-to-date) (running: ${API_REV:-<none>})"

compose build --build-arg REVISION="$REV" web
if [ "$BUILD_API" -eq 1 ]; then
  compose build api worker
fi

SERVICES="web"
[ "$BUILD_API" -eq 1 ] && SERVICES="web api worker"
compose up -d $SERVICES

wait_healthy() { # $@ = services
  local deadline=$((SECONDS + 300)) svc cid status ready
  while true; do
    ready=1
    for svc in "$@"; do
      cid="$(compose ps -q "$svc" 2>/dev/null | head -n1)"
      [ -n "$cid" ] || { ready=0; continue; }
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid")"
      case "$status" in
        unhealthy)
          echo "service $svc is unhealthy" >&2
          compose logs --tail=50 "$svc" >&2 || true
          return 1
          ;;
        healthy) : ;;
        *) ready=0 ;;
      esac
    done
    if [ "$ready" -eq 1 ]; then
      echo "healthy: $*"
      return 0
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "timed out waiting for $* to become healthy" >&2
      return 1
    fi
    sleep 3
  done
}
wait_healthy $SERVICES

# Smoke through the gate. The gate publishes no port, so unless BASE_URL points
# at a reachable endpoint (e.g. the owner's tunnel), run the smoke inside the
# project network against the gate service.
if [ -n "${BASE_URL:-}" ] && command -v node >/dev/null 2>&1; then
  node deploy/nonprod/smoke.mjs "$ENV_NAME"
else
  docker run --rm \
    --network "${PROJECT}_default" \
    -v "$REPO_ROOT/deploy/nonprod/smoke.mjs:/smoke.mjs:ro" \
    -v "${ENV_DIR}:/data/bestmodel/nonprod/${ENV_NAME}:ro" \
    -e BASE_URL="http://gate:80" \
    node:22-alpine \
    node /smoke.mjs "$ENV_NAME"
fi

echo "ship $ENV_NAME ok"
