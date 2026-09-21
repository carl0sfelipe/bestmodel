#!/usr/bin/env bash
# Oracle for specs/en/S36-retire-pages-divergence.md (acceptance 1–5).
# Static files — no server needed. Red before implementation
# (criterion 4: the Pages tour links are still in llms.txt).
set -u
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 2

# 1. the Pages build emits a redirect, not divergent content
grep -rqi 'http-equiv="refresh".*www\.bestmodel\.run\|url=https://www\.bestmodel\.run' apps/web/site/ .github/workflows/ || fail "1 (Pages publishes a redirect)"
# 2. canonical link is present
grep -rqi 'rel="canonical"[^>]*bestmodel\.run' apps/web/site/ || fail "2 (canonical link present)"
# 3. apps/web/site is documented as archived
grep -qi 'archive\|frozen' apps/web/AGENTS.md || fail "3 (apps/web/AGENTS.md marks the archive)"
# 4. contract no longer routes humans to Pages-only tours
if grep -q 'index.html?as=human' apps/web/site/llms.txt; then fail "4 (llms.txt still points at Pages-only tours)"; fi
# 5. contract points humans at web-next
grep -q '/?as=human\|/hardware?as=human' apps/web/site/llms.txt || fail "5 (llms.txt points at web-next routes)"

echo "S36 oracle: PASS (5/5)"
