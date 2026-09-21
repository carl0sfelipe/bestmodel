#!/usr/bin/env bash
# Oracle for specs/en/S47-copy-slop-gate.md (acceptance 1–6).
# Red before implementation at criterion 1 (the gate script does not exist)
# and 4 (wall/hardware/track-record/console/cli/claims still ship <br/>
# headlines in source).
set -u
. "$(dirname "$0")/lib.sh"   # ROOT + fail() — this oracle greps source, no app needed
cd "$ROOT" || exit 2

# 1. gate script exists and is executable
test -x apps/web-next/scripts/slop-gate.sh || fail "1 (scripts/slop-gate.sh executable)"
# 2. gate passes on the reworked tree
bash apps/web-next/scripts/slop-gate.sh || fail "2 (slop-gate clean on tree)"
# 3. self-test: the gate actually catches a planted violation
printf '<h1>It is a ladder<br/>climbed by acts.</h1>\n' > apps/web-next/app/_slop_probe.tsx
if bash apps/web-next/scripts/slop-gate.sh >/dev/null 2>&1; then
  rm -f apps/web-next/app/_slop_probe.tsx
  fail "3 (gate missed a planted violation)"
fi
rm -f apps/web-next/app/_slop_probe.tsx
# 4. no <br/> headline remains anywhere in web-next routes
rg -n '<h[12][^>]*>[^<]*<br' apps/web-next/app && fail "4 (<br headline still in app/)"
# 5. no banned words in routes
rg -niw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' apps/web-next/app && fail "5 (banned word still in app/)"
# 6. gate wired into CI
rg -q 'slop-gate' .github/workflows/ || fail "6 (slop-gate wired into CI)"

echo "S47 oracle: PASS (6/6)"
