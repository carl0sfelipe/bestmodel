#!/usr/bin/env bash
# Oracle for specs/en/S34-console-social-surface.md (acceptance 1–8).
# Static files — no server needed. Red before implementation
# (criterion 1: console.js has no /v1/users/ call today).
set -u
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 2

C=apps/web/console/console.js
H=apps/web/console/index.html

# 1. identity strip wired to the profile endpoint
grep -q '/v1/users/' "$C" || fail "1 (console.js calls /v1/users/)"
# 2. points and tier are rendered
grep -Eq 'points|tier' "$H" || fail "2 (index.html renders points/tier)"
# 3. feed cards carry the author handle and basis badge
grep -q 'handle' "$C" || fail "3a (cards carry author handle)"
grep -q 'basis' "$C" || fail "3b (cards carry basis badge)"
# 4. notifications wired
grep -q '/v1/notifications' "$C" || fail "4 (console.js calls /v1/notifications)"
# 5. follow action wired
grep -q '/follow' "$C" || fail "5 (console.js calls follow)"
# 6. honesty-ladder footer preserved
grep -q 'honesty ladder' "$H" || fail "6 (honesty-ladder footer preserved)"
# 7. no backend touched (diff against main)
git diff --name-only main -- apps/public-api apps/intake-worker infra | grep -q . && fail "7 (backend diff detected)"
# 8. no unknown endpoint introduced
if grep -oE '/v1/[a-z/_{}-]+' "$C" | sort -u | grep -vE '^/v1/(auth|feed|claims|users|notifications|run-claims|cards)' >/dev/null 2>&1; then
  fail "8 (unknown /v1/ endpoint introduced)"
fi

echo "S34 oracle: PASS (8/8)"
