#!/usr/bin/env bash
# Exports the build args the api image bakes in (H12: /v1/health tells the
# truth about what is running). Source it, or use it as a prefix:
#
#   eval "$(deploy/build-args.sh)" && docker compose ... up -d --build api
#
# Prints shell assignments; never mutates anything.
set -euo pipefail
cd "$(dirname "$0")/.."
sha=$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
  sha="${sha}-dirty"
fi
printf 'export BESTMODEL_GIT_SHA=%q\n' "$sha"
printf 'export BESTMODEL_BUILT_AT=%q\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
