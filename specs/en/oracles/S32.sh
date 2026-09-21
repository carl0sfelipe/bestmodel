#!/usr/bin/env bash
# Oracle for specs/en/S32-web-dual-view-mechanism.md (acceptance 1–8).
# Red before implementation (criterion 2 fails: no data-view="agent").
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1. explicit human
curl -s "$BASE/?as=human" | grep -q 'data-view="human"' || fail "1 (?as=human renders data-view=human)"
# 2. explicit agent
curl -s "$BASE/?as=agent" | grep -q 'data-view="agent"' || fail "2 (?as=agent renders data-view=agent)"
# 3. browser default is human
curl -s -A "Mozilla/5.0" "$BASE/" | grep -q 'data-view="human"' || fail "3 (browser default is human)"
# 4. agent UA flips to agent
curl -s -A "GPTBot/1.1" "$BASE/" | grep -q 'data-view="agent"' || fail "4 (agent UA flips to agent)"
# 5. search crawler stays human
curl -s -A "Googlebot/2.1" "$BASE/" | grep -q 'data-view="human"' || fail "5 (crawler stays human)"
# 6. /wall agent twin is monospace text
curl -s "$BASE/wall?as=agent" | grep -q 'data-view="agent"' || fail "6a (/wall?as=agent renders data-view=agent)"
curl -s "$BASE/wall?as=agent" | grep -q '<pre' || fail "6b (/wall?as=agent renders <pre>)"
# 7. resolver + middleware exist
test -f apps/web-next/lib/view.ts && test -f apps/web-next/middleware.ts || fail "7 (lib/view.ts + middleware.ts exist)"
# 8. toggle is in the layout
grep -q 'view-toggle\|ViewToggle' apps/web-next/app/layout.tsx || fail "8 (ViewToggle wired in layout)"

echo "S32 oracle: PASS (8/8)"
