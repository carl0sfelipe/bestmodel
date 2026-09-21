#!/usr/bin/env bash
# Oracle for specs/en/S35-agent-twin-rollout.md (acceptance 1–5).
# Red before implementation (criterion 1 prints MISS for uncovered routes).
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1. every listed route serves an agent twin
missing=0
for r in claims cloud-anchors hardware mural submit track-record; do
  curl -s "$BASE/$r?as=agent" | grep -q 'data-view="agent"' || { echo "MISS $r"; missing=1; }
done
[ "$missing" = "0" ] || fail "1 (every route serves an agent twin)"
# 2. every listed route still serves a human view by default
missing=0
for r in claims cloud-anchors hardware mural submit track-record; do
  curl -s "$BASE/$r" | grep -q 'data-view="human"' || { echo "MISS-HUMAN $r"; missing=1; }
done
[ "$missing" = "0" ] || fail "2 (every route keeps its human view)"
# 3. agent twins are monospace text
curl -s "$BASE/claims?as=agent" | grep -q '<pre' || fail "3 (agent twin renders <pre>)"
# 4. a dynamic route twin renders a real record — pick the first model slug
#    from the /wall twin's data lines (column 2), then load /m/<slug>?as=agent
slug="$(curl -s "$BASE/wall?as=agent" | grep -E '\| n=[0-9]+$' | head -1 | cut -d'|' -f2 | tr -d ' ')"
[ -n "$slug" ] || fail "4a (wall twin exposes a model slug)"
curl -s "$BASE/m/$slug?as=agent" | grep -q 'data-view="agent"' || fail "4b (/m/$slug?as=agent renders agent twin)"
# 5. contract lists routes with their twins
grep -qi '^## Routes' apps/web/site/llms.txt || fail "5a (llms.txt has a Routes section)"
grep -q '?as=agent' apps/web/site/llms.txt || fail "5b (llms.txt lists ?as=agent twins)"

echo "S35 oracle: PASS (5/5)"
