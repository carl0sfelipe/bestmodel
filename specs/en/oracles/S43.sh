#!/usr/bin/env bash
# Oracle for specs/en/S43-design-system-and-home-craft.md (acceptance 1–8).
# Red before implementation at criterion 3 (design.md/tokens.css do not exist)
# and 7 (the home ships no ecosystem SVG). Note: the home today splits its
# headlines with <em>, not <br/>, so criterion 4 is already green pre-rework —
# the red state is the missing locked system, not a literal <br/> (amendment
# recorded in the spec's Oráculo narrative).
set -u
. "$(dirname "$0")/lib.sh"
ensure_app || exit 3

# 1–2. the ?as= contract is untouched (L04 S32 stays green)
curl -s "$BASE/?as=human" | grep -q 'data-view="human"' || fail "1 (home human view)"
curl -s "$BASE/?as=agent" | grep -q 'data-view="agent"' || fail "2 (home agent twin)"
# 3. the locked design system exists
test -f apps/web-next/design.md || fail "3a (apps/web-next/design.md)"
test -f apps/web-next/tokens.css || fail "3b (apps/web-next/tokens.css)"
# 4. no mid-headline break on the home
curl -s "$BASE/" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br' && fail "4 (<br inside h1/h2 on home)"
# 5. no banned words / binary contrasts on the home
curl -s "$BASE/" | grep -Eiqw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' && fail "5a (banned word on home)"
curl -s "$BASE/" | grep -Eiq "isn't .+ it's|not just .+ but|it's not .+ it's" && fail "5b (binary contrast on home)"
# 6. basis still declared (honesty intact)
curl -s "$BASE/" | grep -Eq 'measured|reported|no data yet' || fail "6 (basis labels on home)"
# 7. the ecosystem diagram is a hand-built inline SVG, not fake chrome
curl -s "$BASE/" | grep -q '<svg' || fail "7a (ecosystem SVG on home)"
curl -s "$BASE/" | grep -Eiq 'traffic-light|window-dots|fake-terminal' && fail "7b (fake chrome on home)"
# 8. the S43 hallmark stamp in the reworked CSS
grep -Eq 'Hallmark · pre-emit critique: P[3-5] H[3-5] E[3-5] S[3-5] R[3-5] V[3-5]' apps/web-next/app/globals.css || fail "8 (pre-emit critique stamp)"

echo "S43 oracle: PASS (8/8)"
