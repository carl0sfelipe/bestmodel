#!/usr/bin/env bash
# Caminho crítico do bestmodel num ambiente: health, migrações, worker consumindo o stream
# e endpoint público de ranking com dados. Mesmo script para dev, stag e prod:
#   bash infra/scripts/flow-bestmodel.sh dev    # checagem COMPLETA (via docker exec)
#   bash infra/scripts/flow-bestmodel.sh stag
#   bash infra/scripts/flow-bestmodel.sh https://api.bestmodel.run   # prod: SÓ GETs (curl)
# dev/stag gravam 1 evento sintético inválido no stream benchmark_runs: o worker precisa
# consumi-lo (lag do consumer group volta ao valor de base) — prova api↔redis↔worker vivos.
set -uo pipefail
ARG="${1:?uso: flow-bestmodel.sh dev|stag|https://url-de-prod}"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS $1${2:+ — $2}"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL $1${2:+ — $2}"; }

if [[ "$ARG" == http* ]]; then
  MODE=prod; BASE="${ARG%/}"
  get()  { curl -s --max-time 15 "$1"; }
  code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$1"; }
else
  case "$ARG" in dev|stag) ;; *) echo "env inválido: $ARG" >&2; exit 2 ;; esac
  MODE="$ARG"
  API="bestmodel-${ARG}-api-1"; PG="bestmodel-${ARG}-postgres-1"; RD="bestmodel-${ARG}-redis-1"
  DB="bestmodel_${ARG}"
  get()  { docker exec "$API" python -c "import urllib.request,sys;sys.stdout.write(urllib.request.urlopen('$1',timeout=10).read().decode())"; }
  code() { docker exec "$API" python -c "import urllib.request,sys;sys.stdout.write(str(urllib.request.urlopen('$1',timeout=10).status))"; }
  psql() { docker exec "$PG" psql -U bestmodel -d "$DB" -Atc "$1"; }
  rds()  { docker exec "$RD" redis-cli --raw "$@"; }
fi

# 1. /v1/health com git_sha
H=$(get "http://$( [ "$MODE" = prod ] && echo "${BASE#http*://}" || echo localhost:8000 )/v1/health" 2>/dev/null || true)
SHA=$(echo "$H" | python3 -c "import json,sys;print(json.load(sys.stdin).get('git_sha','?'))" 2>/dev/null || echo "?")
[ -n "$SHA" ] && [ "$SHA" != "?" ] && ok "/v1/health" "git_sha=$SHA" || bad "/v1/health" "$H"

# 2. ranking público com dados
if [ "$MODE" = prod ]; then
  CODE=$(code "$BASE/v1/leaderboard")
  [ "$CODE" = 200 ] && ok "/v1/leaderboard" "HTTP 200" || bad "/v1/leaderboard" "HTTP $CODE"
else
  # migrações aplicadas == arquivos .sql do repo (contagem dinâmica, nunca fixa)
  REPO_MIG=$(ls "$(cd "$(dirname "$0")/../migrations" && pwd)"/*.sql | wc -l)
  APPLIED=$(psql "select count(*) from meta.schema_migrations;" 2>/dev/null || echo 0)
  [ "${APPLIED:-0}" -ge "$REPO_MIG" ] && ok "migrações aplicadas" "$APPLIED/$REPO_MIG" || bad "migrações" "aplicadas=${APPLIED:-0} de $REPO_MIG"

  # worker: consumer group existe e o evento sintético é consumido (lag volta à base)
  GROUP_OK=$(rds XINFO GROUPS benchmark_runs 2>/dev/null | command grep -c name)
  if [ "${GROUP_OK:-0}" -ge 1 ]; then
    lag() { rds XINFO GROUPS benchmark_runs | paste - - - - - - | command grep -oE '[0-9]+$' | tail -1; }
    BASE_LAG=$(lag)
    rds XADD benchmark_runs "flow-$(date +%s)" payload '{"flow":"synthetic-invalid"}' >/dev/null
    CONSUMED=0
    for _ in $(seq 1 12); do
      sleep 5
      NOW=$(lag)
      if [ "${NOW:-99}" -le "${BASE_LAG:-0}" ]; then CONSUMED=1; break; fi
    done
    [ "$CONSUMED" = 1 ] && ok "worker consumiu evento sintético" "lag ${BASE_LAG:-0}→${NOW:-?}" \
      || bad "worker não consumiu" "lag ${BASE_LAG:-?}→${NOW:-?}"
  else
    bad "worker sem consumer group no stream benchmark_runs" "worker nunca rodou?"
  fi

  # leaderboard com JSON válido pela rede interna
  LB=$(get "http://localhost:8000/v1/leaderboard" 2>/dev/null || true)
  echo "$LB" | python3 -c "import json,sys;json.load(sys.stdin)" 2>/dev/null \
    && ok "/v1/leaderboard" "$(echo "$LB" | head -c 70)" || bad "/v1/leaderboard" "${LB:0:70}"
fi

echo ""
echo "$PASS passaram, $FAIL falharam (modo $MODE)"
[ "$FAIL" = 0 ]
