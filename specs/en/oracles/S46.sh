#!/usr/bin/env bash
# Oracle for specs/en/S46-claims-page-craft.md (acceptance 1–5).
# Red before implementation at criterion 4 (the /claims page-head ships
# "Every number gets a home<br />and a source.").
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1. human view
curl -s "$BASE/claims?as=human" | grep -q 'data-view="human"' || fail "1 (/claims human view)"
# 2. L04 twin still green
curl -s "$BASE/claims?as=agent" | grep -q 'data-view="agent"' || fail "2 (/claims agent twin)"
# 3. feed carries basis badges
curl -s "$BASE/claims" | grep -Eq 'measured|reported|unvalidated|claim' || fail "3 (basis badges on /claims)"
# 4. no mid-headline break (red today: the shared page-head)
curl -s "$BASE/claims" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br' && fail "4 (<br inside h1/h2 on /claims)"
# 5. no banned words / binary contrasts
curl -s "$BASE/claims" | grep -Eiqw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' && fail "5a (banned word on /claims)"
curl -s "$BASE/claims" | grep -Eiq "isn't .+ it's|not just .+ but|it's not .+ it's" && fail "5b (binary contrast on /claims)"

echo "S46 oracle: PASS (5/5)"
