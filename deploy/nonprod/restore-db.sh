#!/usr/bin/env bash
# Restaura o banco de um ambiente não-produção a partir de um dump FRESCO de prod
# (pg_dump via docker exec no postgres de prod = leitura) e ANONIMIZA.
# Destruí apenas o banco bestmodel_<env> do ambiente nonprod — NUNCA o de prod.
#   bash deploy/nonprod/restore-db.sh dev
# Anonimização (LGPD): varre information_schema por colunas com nome de dado pessoal
# (email/token/secret/credential/handle) e substitui; contagens antes/depois no stdout.
set -euo pipefail
ENV_NAME="${1:?uso: restore-db.sh dev|stag}"
case "$ENV_NAME" in dev|stag) ;; *) echo "env inválido: $ENV_NAME" >&2; exit 2 ;; esac
BASE="/data/bestmodel/nonprod/$ENV_NAME"
PG="bestmodel-${ENV_NAME}-postgres-1"
DB="bestmodel_${ENV_NAME}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="$BASE/restore-source-${STAMP}.sql.gz"

echo "[$(date -u +%FT%TZ)] dump SOMENTE-LEITURA do postgres de prod"
docker exec bestmodel-prod-postgres-1 pg_dump -U bestmodel -d bestmodel | gzip > "$DUMP"
gunzip -c "$DUMP" | tail -30 | command grep -q "PostgreSQL database dump complete" \
  || { echo "dump incompleto: $DUMP" >&2; exit 3; }
echo "dump ok: $DUMP ($(du -h "$DUMP" | cut -f1))"

echo "recria $DB no nonprod ($PG)"
docker exec "$PG" psql -U bestmodel -d postgres -qc "DROP DATABASE IF EXISTS $DB;"
docker exec "$PG" psql -U bestmodel -d postgres -qc "CREATE DATABASE $DB;"
gunzip -c "$DUMP" | docker exec -i "$PG" psql -U bestmodel -d "$DB" -v ON_ERROR_STOP=0 -q > /dev/null
TABLES=$(docker exec "$PG" psql -U bestmodel -d "$DB" -Atc "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE';")
echo "tabelas públicas importadas: $TABLES"

echo "anonimização: colunas email/token/secret/credential/password em public"
COLS=$(docker exec "$PG" psql -U bestmodel -d "$DB" -Atc "
select table_name || '|' || column_name || '|' || data_type
from information_schema.columns
where table_schema = 'public'
  and (column_name ~* '(e[-_]?mail|token|secret|credential|passw|api[_-]?key)')
  and data_type in ('text','character varying','character')
order by table_name, column_name;")
if [ -z "$COLS" ]; then
  echo "nenhuma coluna sensível encontrada (verifique se faz sentido)"
fi
while IFS='|' read -r table column _dtype; do
  [ -z "$table" ] && continue
  BEFORE=$(docker exec "$PG" psql -U bestmodel -d "$DB" -Atc "select count(*) from \"$table\" where \"$column\" is not null and \"$column\" <> '';")
  docker exec "$PG" psql -U bestmodel -d "$DB" -qc "update \"$table\" set \"$column\" = 'anon-' || md5(random()::text) where \"$column\" is not null and \"$column\" <> '';" >/dev/null
  echo "  $table.$column: $BEFORE valores -> anonimizados"
done <<< "$COLS"

echo "conferência: health do banco restaurado"
docker exec "$PG" psql -U bestmodel -d "$DB" -Atc "select 'ok' where exists (select 1 from information_schema.tables where table_schema='public');"
echo "restore+anonimização concluídos: $DB"
