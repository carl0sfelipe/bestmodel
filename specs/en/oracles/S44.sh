#!/usr/bin/env bash
# Oracle for specs/en/S44-cli-page-craft.md (acceptance 1–6, as amended
# 2026-09-21: the spec was written against origin/main, before L05 landed —
# the whole loop now dispatches, so criterion 3 is the D10 inverse
# 'documented ⟹ dispatched', not a 'not shipped' quarantine grep).
# Red before implementation at criterion 4 (the /cli page-head ships
# "From clone to<br />measured numbers.").
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3
cd "$ROOT" || exit 3

# 1. human view
curl -s "$BASE/cli?as=human" | grep -q 'data-view="human"' || fail "1 (/cli human view)"
# 2. L04 S33 literal strings preserved (they are the real commands)
curl -s "$BASE/cli" | grep -q 'benchmark-probe' || fail "2a (benchmark-probe on /cli)"
curl -s "$BASE/cli" | grep -q 'agent-smoke' || fail "2b (agent-smoke on /cli)"
# 3. D10 inverse (amended 2026-09-21, L05): every subcommand the page
#    documents dispatches in the built binary.
for c in lab plan report contribute login; do
  if curl -s "$BASE/cli" | grep -q "$c"; then
    ./target/release/benchmark-probe "$c" --help >/dev/null 2>&1 || fail "3 ($c documented on /cli but not dispatched)"
  fi
done
# 4. no mid-headline break (red today: the shared page-head)
curl -s "$BASE/cli" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br' && fail "4 (<br inside h1/h2 on /cli)"
# 5. no banned words / binary contrasts
curl -s "$BASE/cli" | grep -Eiqw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' && fail "5a (banned word on /cli)"
curl -s "$BASE/cli" | grep -Eiq "isn't .+ it's|not just .+ but|it's not .+ it's" && fail "5b (binary contrast on /cli)"
# 6. real code block, no fake chrome
curl -s "$BASE/cli" | grep -q '<pre' || fail "6a (real <pre> code block on /cli)"
curl -s "$BASE/cli" | grep -Eiq 'traffic-light|window-dots|fake-terminal' && fail "6b (fake chrome on /cli)"

echo "S44 oracle: PASS (6/6)"
