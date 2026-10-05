#!/usr/bin/env bash
# Offline self-tests for the nonprod web tooling. No builds, no network:
#   1. bash -n on the deploy/nonprod scripts
#   2. node --check on smoke.mjs
#   3. init-env into a scratch BM_DATA_ROOT: Caddyfile with both handle blocks
#      is created, and a second run does not overwrite it
#   4. docker compose config -q (dev+devlive and stag) — only when docker exists
#   5. deploy/docker-compose.prod.yml unchanged vs HEAD
set -euo pipefail

cd "$(dirname "$0")/../.."
FAIL=0
fail() { echo "FAIL: $*" >&2; FAIL=1; }
pass() { echo "ok: $*"; }

# 1. Script syntax.
for script in deploy/nonprod/init-env.sh deploy/nonprod/dev-live.sh deploy/nonprod/ship.sh; do
  bash -n "$script" || fail "bash -n $script"
done
if [ "$FAIL" -eq 0 ]; then pass "bash -n deploy/nonprod scripts"; else exit 1; fi

# 2. smoke.mjs syntax.
node --check deploy/nonprod/smoke.mjs || fail "node --check smoke.mjs"
if [ "$FAIL" -eq 0 ]; then pass "node --check smoke.mjs"; else exit 1; fi

# 3. init-env into a scratch root.
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT
BM_DATA_ROOT="$TMP_ROOT" bash deploy/nonprod/init-env.sh dev || fail "init-env dev (first run)"
CF="$TMP_ROOT/nonprod/dev/Caddyfile"
[ -s "$CF" ] || fail "Caddyfile was not created"
grep -q 'handle /v1/' "$CF" || fail "Caddyfile missing the /v1/* handle"
grep -qE '^[[:space:]]*handle[[:space:]]*\{[[:space:]]*$' "$CF" || fail "Caddyfile missing the default handle"
grep -q 'basic_auth' "$CF" || fail "Caddyfile missing basic_auth"
grep -q 'X-Robots-Tag' "$CF" || fail "Caddyfile missing X-Robots-Tag"
grep -q 'reverse_proxy web:3000' "$CF" || fail "Caddyfile does not route the default handle to web:3000"
grep -q '^WEB_DOMAIN=dev\.bestmodel\.run$' "$TMP_ROOT/nonprod/dev/compose.env" || fail "compose.env missing WEB_DOMAIN=dev.bestmodel.run"
SUM_BEFORE="$(sha256sum "$CF" | cut -d' ' -f1)"
BM_DATA_ROOT="$TMP_ROOT" bash deploy/nonprod/init-env.sh dev || fail "init-env dev (second run)"
SUM_AFTER="$(sha256sum "$CF" | cut -d' ' -f1)"
[ "$SUM_BEFORE" = "$SUM_AFTER" ] || fail "second init-env run overwrote the Caddyfile"
pass "init-env: Caddyfile with both handles created, not overwritten on re-run"
BM_DATA_ROOT="$TMP_ROOT" bash deploy/nonprod/init-env.sh stag || fail "init-env stag"

# 4. compose config — client-side only, needs just the docker CLI.
if command -v docker >/dev/null 2>&1; then
  BM_ENV=dev docker compose -p bestmodel-dev \
    -f deploy/docker-compose.prod.yml \
    -f deploy/docker-compose.nonprod.yml \
    -f deploy/docker-compose.devlive.yml \
    --env-file "$TMP_ROOT/nonprod/dev/compose.env" \
    config -q || fail "docker compose config (dev + devlive overlay)"
  BM_ENV=stag docker compose -p bestmodel-stag \
    -f deploy/docker-compose.prod.yml \
    -f deploy/docker-compose.nonprod.yml \
    --env-file "$TMP_ROOT/nonprod/stag/compose.env" \
    config -q || fail "docker compose config (stag)"
  pass "docker compose config (dev+devlive, stag)"
else
  echo "skip: docker CLI not found — compose config checks skipped"
fi

# 5. prod compose must be untouched.
git diff --quiet HEAD -- deploy/docker-compose.prod.yml || fail "deploy/docker-compose.prod.yml differs from HEAD"
pass "prod compose unchanged vs HEAD"

if [ "$FAIL" -ne 0 ]; then
  echo "nonprod self-tests FAILED" >&2
  exit 1
fi
echo "all nonprod self-tests passed"
