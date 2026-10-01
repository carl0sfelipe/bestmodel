#!/usr/bin/env bash
# Promove para PRODUÇÃO a imagem que passou no stag. Dry-run é o padrão;
# nesta spec (dev/stag) só o dry-run roda — o --apply sai se BM_PROMOTE_ALLOW != yes.
#   bash deploy/promote-prod.sh            # plano e checagens
#   BM_PROMOTE_ALLOW=yes bash deploy/promote-prod.sh --apply   # só quando o Carlos mandar
#
# Ordem do --apply: backup-db -> tag :rollback-<ts> -> build args do git ->
# up -d --no-build api worker com a imagem testada -> smoke com retry 6x10s.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPLY="${1:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
PROD=(docker compose -p bestmodel-prod -f "$ROOT/deploy/docker-compose.prod.yml" -f "$ROOT/deploy/docker-compose.omarchy.yml" --env-file "$ROOT/deploy/.env")

echo "HEAD: $(git -C "$ROOT" rev-parse --short HEAD)"
[ -n "$(git -C "$ROOT" status --porcelain)" ] && { echo "árvore com mudanças não commitadas — commit antes de promover" >&2; exit 2; }

DEV_IMG=$(docker inspect -f '{{.Image}}' bestmodel-dev-api-1 2>/dev/null || echo missing)
STAG_IMG=$(docker inspect -f '{{.Image}}' bestmodel-stag-api-1 2>/dev/null || echo missing)
[ "$DEV_IMG" = "$STAG_IMG" ] && [ "$DEV_IMG" != missing ] \
  && echo "mesma imagem dev==stag: ${DEV_IMG:0:19}…" || { echo "dev e stag com imagens DIFERENTES (ou fora do ar) — não promove" >&2; exit 3; }
STAG_SHA=$(docker exec bestmodel-stag-api-1 python -c "import urllib.request;print(__import__('json').loads(urllib.request.urlopen('http://localhost:8000/v1/health',timeout=5).read())['git_sha'])")
echo "imagem do stag: git_sha=$STAG_SHA"

bash "$ROOT/infra/scripts/flow-bestmodel.sh" stag

if [ "$APPLY" != "--apply" ]; then
  echo "DRY RUN ok. --apply faria: backup-db → tag bestmodel-prod-api:rollback-$STAMP → up -d --no-build api worker → smoke 6x10s em https://api.bestmodel.run/v1/health."
  exit 0
fi
if [ "${BM_PROMOTE_ALLOW:-}" != yes ]; then
  echo "--apply bloqueado nesta spec: prod é só leitura. O Carlos decide quando subir." >&2
  exit 4
fi

bash "$ROOT/deploy/scripts/backup-db.sh"
docker tag bestmodel-prod-api:latest "bestmodel-prod-api:rollback-$STAMP"
# a imagem que passa no stag É a que sobe: retag, nunca rebuild em prod
docker tag bestmodel-stag-api:latest bestmodel-prod-api:latest
"${PROD[@]}" up -d --no-build api worker

# smoke com retry (lição do orbe: índice/cache refeito no deploy pode dar falso negativo)
fail=1
for i in $(seq 1 6); do
  sleep 10
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://api.bestmodel.run/v1/health || echo 000)
  [ "$CODE" = 200 ] && { fail=0; break; }
  echo "tentativa $i/6: /v1/health → $CODE"
done
if [ "$fail" = 1 ]; then
  echo "SMOKE FALHOU. Rollback: docker tag bestmodel-prod-api:rollback-$STAMP bestmodel-prod-api:latest; ${PROD[*]} up -d --no-build api worker"
  exit 1
fi
echo "PROMOÇÃO OK (git_sha=$STAG_SHA). Rollback: bestmodel-prod-api:rollback-$STAMP"
