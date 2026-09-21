#!/usr/bin/env bash
# Oracle for specs/en/S45-wall-page-craft.md (acceptance 1–6).
# Red before implementation at criterion 5 (the /wall page-head ships
# "What the community<br />actually measures.").
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1. human view
curl -s "$BASE/wall?as=human" | grep -q 'data-view="human"' || fail "1 (/wall human view)"
# 2. L04 twin still green
curl -s "$BASE/wall?as=agent" | grep -q 'data-view="agent"' || fail "2a (/wall agent twin)"
curl -s "$BASE/wall?as=agent" | grep -q '<pre' || fail "2b (/wall agent twin renders <pre>)"
# 3. data leads (a real table on the human view)
curl -s "$BASE/wall" | grep -Eiq '<table|role="table"|wall-list' || fail "3 (data table leads on /wall)"
# 4. basis preserved
curl -s "$BASE/wall" | grep -Eq 'measured|reported' || fail "4 (basis labels on /wall)"
# 5. old slop headline gone (red today)
curl -s "$BASE/wall" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br' && fail "5a (<br inside h1/h2 on /wall)"
curl -s "$BASE/wall" | grep -iq 'What the community' && fail "5b (old slop headline on /wall)"
# 6. no banned words
curl -s "$BASE/wall" | grep -Eiqw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' && fail "6 (banned word on /wall)"

echo "S45 oracle: PASS (6/6)"
