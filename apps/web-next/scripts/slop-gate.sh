#!/usr/bin/env bash
# slop-gate.sh — the no-ai-slop copy gate (S47, L06 human-craft pass).
# Fails (exit 1) on any banned copy pattern in apps/web-next/app/**/*.{tsx,ts},
# printing file:line for every hit. The list mirrors the ban-list in
# specs/en/S43-design-system-and-home-craft.md and design.md.
#
# Rules of the house (S47): de-slop means rewriting, never suppressing —
# commenting out a headline, or moving copy into a file this gate does not
# scan, is dodging the grep. If a new surface carries prose (data files
# included), extend the scan, not the exemption list.
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" >/dev/null 2>&1
APP=apps/web-next/app

status=0

# 1. Mid-headline break: a <br inside an <h1>/<h2> (-U: the tag's text can
#    span source lines).
rg -Un --no-heading -n '<h[12][^>]*>[^<]*<br' "$APP" --glob '*.{tsx,ts}' && status=1

# 2. Banned words (whole-word, case-insensitive).
rg -niw --no-heading 'delve|leverage|utilize|facilitate|robust|seamless|elevate|embark|supercharge|harness|unlock|realm|tapestry|paradigm|game.?changer|cutting.?edge|ever.?evolving|transformative' "$APP" --glob '*.{tsx,ts}' && status=1

# 3. Binary contrasts (line-scoped: these shapes live inside one string).
rg -ni --no-heading "isn't .+ it's|it's not .+ it's|not just .+ but" "$APP" --glob '*.{tsx,ts}' && status=1

# 4. Colon-reveal drama: a heading of the shape "Noun phrase: lowercase reveal".
rg -n --no-heading '<h[1-3][^>]*>[A-Za-z][^<>{}]{2,60}: [a-z]' "$APP" --glob '*.{tsx,ts}' && status=1

# 5. Throat-clearing openers.
rg -ni --no-heading "here's the thing|here's what|let me be clear|the truth is|the reality is" "$APP" --glob '*.{tsx,ts}' && status=1

if [ "$status" -ne 0 ]; then
  echo "slop-gate: banned copy pattern(s) above — rewrite the copy, do not suppress the gate." >&2
  exit 1
fi
echo "slop-gate: clean"
