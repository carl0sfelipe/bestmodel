#!/usr/bin/env bash
# Live web-next loop on the DEV stack: `next dev` with the repo bind-mounted
# read-only at /repo (deploy/docker-compose.devlive.yml), so edits show up in
# seconds. node_modules/.next are anonymous volumes seeded from the image
# install, so the read-only bind mount never shadows them.
#
#   bash deploy/nonprod/dev-live.sh up      # build + (re)create web, wait for health
#   bash deploy/nonprod/dev-live.sh logs    # follow web-next logs
#   bash deploy/nonprod/dev-live.sh image   # show the web image + revision
#
# After a lockfile change, drop the container first so the anonymous
# node_modules volume is re-seeded from the new image:
#   docker compose -p bestmodel-dev down web
set -euo pipefail

ENV_NAME="dev"
PROJECT="bestmodel-${ENV_NAME}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

usage() {
  echo "usage: dev-live.sh up|logs|image" >&2
  exit 2
}
CMD="${1:-}"
case "$CMD" in up|logs|image) ;; *) usage ;; esac

cd "$REPO_ROOT"

compose() {
  docker compose -p "$PROJECT" \
    -f deploy/docker-compose.prod.yml \
    -f deploy/docker-compose.nonprod.yml \
    -f deploy/docker-compose.devlive.yml \
    --env-file "/data/bestmodel/nonprod/${ENV_NAME}/compose.env" \
    "$@"
}

container_id() { # $1 = service
  compose ps -q "$1" 2>/dev/null | head -n1
}

wait_healthy() { # $@ = services
  local deadline=$((SECONDS + 240)) svc cid status ready
  while true; do
    ready=1
    for svc in "$@"; do
      cid="$(container_id "$svc")"
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

case "$CMD" in
  up)
    compose build web
    compose up -d --force-recreate web
    wait_healthy web
    echo "dev live loop up — edits appear on next request; logs: bash deploy/nonprod/dev-live.sh logs"
    ;;
  logs)
    compose logs -f --tail=100 web
    ;;
  image)
    cid="$(container_id web)"
    [ -n "$cid" ] || { echo "web container is not running (start it: bash deploy/nonprod/dev-live.sh up)" >&2; exit 1; }
    img="$(docker inspect --format '{{.Image}}' "$cid")"
    echo "container: ${PROJECT} web"
    echo "image:     $img"
    rev="$(docker image inspect "$img" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true)"
    echo "revision:  ${rev:-<none — devlive target carries no revision label>}"
    ;;
esac
