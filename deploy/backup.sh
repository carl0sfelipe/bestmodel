#!/usr/bin/env bash
# backup.sh — copia off-host do estado de produção do bestmodel.
#
# Por que existe: o Postgres de produção vive num volume docker no único disco
# do beelink. Disco morre = os claims, contas e reputação morrem junto. Este
# script tira a cópia e empurra para um repositório privado no GitHub.
#
# O banco não guarda segredo em texto: auth_token e contributor_account
# guardam hash, webauthn e signing_key guardam chave PÚBLICA. Por isso o dump
# vai sem criptografia — verificado em 2026-08-31 (0 contas, 0 passkeys).
# Se algum dia entrar coluna com segredo em texto, ISTO PRECISA MUDAR.
#
# Uso: deploy/backup.sh [caminho-do-clone]   (default ~/Work/bestmodel-backups)
set -euo pipefail

CLONE="${1:-$HOME/Work/bestmodel-backups}"
PG_CONTAINER="bestmodel-prod-postgres-1"
API_CONTAINER="bestmodel-prod-api-1"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

[ -d "$CLONE/.git" ] || { echo "backup.sh: $CLONE não é um clone git" >&2; exit 1; }
docker inspect "$PG_CONTAINER" >/dev/null 2>&1 || { echo "backup.sh: container $PG_CONTAINER não está no ar" >&2; exit 1; }

PG_USER="$(docker exec "$PG_CONTAINER" printenv POSTGRES_USER)"
PG_DB="$(docker exec "$PG_CONTAINER" printenv POSTGRES_DB)"

# ---- 1. dump do banco -------------------------------------------------------
# Sem compressão de propósito: SQL em texto deixa o git fazer delta entre dias.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" --clean --if-exists > "$TMP/bestmodel.sql"

# Trava: backup vazio ou truncado NÃO entra. Um dump bom termina com o marcador
# do pg_dump; sem ele o arquivo é lixo e commitá-lo destruiria a cópia boa.
grep -q "PostgreSQL database dump complete" "$TMP/bestmodel.sql" \
  || { echo "backup.sh: dump incompleto — nada foi commitado" >&2; exit 1; }
TABLES="$(grep -c '^CREATE TABLE' "$TMP/bestmodel.sql" || true)"
[ "$TABLES" -gt 0 ] || { echo "backup.sh: dump sem nenhuma tabela — nada foi commitado" >&2; exit 1; }

# ---- 2. volume de artefatos -------------------------------------------------
# As runs assinadas (a prova da escada de honestidade) vivem fora do Postgres.
docker run --rm -v bestmodel-prod_artifacts:/a -v "$TMP":/out alpine \
  tar czf /out/artifacts.tar.gz -C /a . 2>/dev/null || : > "$TMP/artifacts.tar.gz"

# ---- 3. commit --------------------------------------------------------------
mv "$TMP/bestmodel.sql" "$CLONE/bestmodel.sql"
mv "$TMP/artifacts.tar.gz" "$CLONE/artifacts.tar.gz"

{
  echo "# bestmodel-backups"
  echo
  echo "Cópia off-host da produção. Gerado por \`deploy/backup.sh\` no repo bestmodel."
  echo
  echo "- Último backup: $STAMP"
  echo "- Tabelas no dump: $TABLES"
  echo "- Tamanho do dump: $(du -h "$CLONE/bestmodel.sql" | cut -f1)"
  echo
  echo "## Restaurar"
  echo
  echo '```'
  echo "docker exec -i $PG_CONTAINER psql -U $PG_USER -d $PG_DB < bestmodel.sql"
  echo "docker run --rm -v bestmodel-prod_artifacts:/a -v \"\$PWD\":/in alpine tar xzf /in/artifacts.tar.gz -C /a"
  echo "docker restart $API_CONTAINER"
  echo '```'
  echo
  echo "O dump usa --clean --if-exists: restaurar por cima de um banco existente"
  echo "derruba os objetos antigos antes de recriar."
} > "$CLONE/README.md"

cd "$CLONE"
git add -A
if git diff --cached --quiet; then
  echo "backup.sh: nada mudou desde o último backup ($STAMP)"
  exit 0
fi
git commit -q -m "backup $STAMP ($TABLES tabelas)"
git push -q origin HEAD
echo "backup.sh: enviado — $TABLES tabelas, $(du -h bestmodel.sql | cut -f1), $STAMP"
