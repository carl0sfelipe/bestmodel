#!/usr/bin/env bash
# lib.sh — shared helper for the L04 story oracles.
# Every oracle that curls the app needs it up on :3000. ensure_app brings it
# up (building first if needed) and leaves it running for the next oracle.
# Local-only: the app serves static pool data, no API or network needed.

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "oracle: not inside the bestmodel git repo" >&2; exit 2; }
# Port is environment, not contract: BM_PORT defaults to the spec's :3000 and
# can be overridden where another app already owns the port (BM_PORT=3210).
PORT="${BM_PORT:-3000}"
BASE="http://localhost:$PORT"

http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$1" 2>/dev/null || echo 000; }

ensure_app() {
  [ "$(http_code "$BASE/")" = "200" ] && return 0
  echo "oracle: app not answering on $BASE — bringing it up (first build can take ~1 min)…" >&2
  cd "$ROOT/apps/web-next" || return 1
  if [ ! -f .next/BUILD_ID ]; then
    echo "oracle: no build output — running next build…" >&2
    npm run build >/tmp/bm-next-build.log 2>&1 || { echo "oracle: build failed — see /tmp/bm-next-build.log" >&2; return 1; }
  fi
  nohup env PORT="$PORT" npm start >>/tmp/bm-next-start.log 2>&1 &
  echo $! >/tmp/bm-next.pid
  local i code
  for i in $(seq 1 90); do
    code="$(http_code "$BASE/")"
    [ "$code" = "200" ] && return 0
    sleep 1
  done
  echo "oracle: app did not come up — see /tmp/bm-next-start.log" >&2
  return 1
}

# fail <criterion> — a missed criterion is a failed oracle (first miss exits).
fail() { echo "FAIL criterion $1" >&2; exit 1; }
