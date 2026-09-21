#!/usr/bin/env bash
# Oracle for specs/en/S33-cli-getting-started-route.md (acceptance 1–8).
# Red before implementation (criterion 1: /cli returns 404).
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1. route exists (was 404)
[ "$(http_code "$BASE/cli")" = "200" ] || fail "1 (/cli returns 200)"
# 2. documents the real CLI
curl -s "$BASE/cli" | grep -q 'benchmark-probe' || fail "2a (mentions benchmark-probe)"
curl -s "$BASE/cli" | grep -q 'agent-smoke' || fail "2b (mentions agent-smoke)"
# 3. unshipped subcommands quarantined, not runnable
curl -s "$BASE/cli" | grep -iq 'not shipped\|in construction' || fail "3 (not-shipped quarantine block)"
# 4. nav points to it
grep -q '"/cli"' apps/web-next/app/layout.tsx || fail "4 (nav has /cli)"
# 5. agent twin (needs S32)
curl -s "$BASE/cli?as=agent" | grep -q 'data-view="agent"' || fail "5 (/cli?as=agent renders agent twin)"
# 6. phantom installer is gone
if grep -rn 'canirun.it/sh' apps/web/ >/dev/null 2>&1; then fail "6 (canirun.it/sh still present in apps/web/)"; fi
# 7. contract keeps the honest line
grep -q 'no one-line installer yet' apps/web/site/llms.txt || fail "7 (llms.txt keeps honest installer line)"
# 8. contract lists the new route
grep -q '/cli' apps/web/site/llms.txt || fail "8 (llms.txt lists /cli)"

echo "S33 oracle: PASS (8/8)"
