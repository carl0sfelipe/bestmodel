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
# 3. D10 inverse (amendment 2026-09-21, L05): the quarantine block retired
#    when plan/report/contribute/login shipped — the standing invariant is
#    'every subcommand the page documents dispatches in the binary'.
for c in lab plan report contribute login; do
  if curl -s "$BASE/cli" | grep -q "$c"; then
    ./target/release/benchmark-probe "$c" --help >/dev/null 2>&1 || fail "3 ($c documented on /cli but not dispatched)"
  fi
done
# 4. nav points to it
grep -q '"/cli"' apps/web-next/app/layout.tsx || fail "4 (nav has /cli)"
# 5. agent twin (needs S32)
curl -s "$BASE/cli?as=agent" | grep -q 'data-view="agent"' || fail "5 (/cli?as=agent renders agent twin)"
# 6. phantom installer is gone from every SHIPPED surface (site/, console/,
#    web-next). apps/web/prototypes/ is out of scope: never deployed, and the
#    S33 diff contract limits this story to site/* + console + web-next
#    (amendment recorded in specs/en/S33-cli-getting-started-route.md).
if grep -rn 'canirun.it/sh' apps/web/site/ apps/web/console/ apps/web-next/ >/dev/null 2>&1; then fail "6 (canirun.it/sh still present in a shipped surface)"; fi
# 7. contract keeps the honest line
grep -q 'no one-line installer yet' apps/web/site/llms.txt || fail "7 (llms.txt keeps honest installer line)"
# 8. contract lists the new route
grep -q '/cli' apps/web/site/llms.txt || fail "8 (llms.txt lists /cli)"

echo "S33 oracle: PASS (8/8)"
