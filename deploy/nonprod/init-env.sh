#!/usr/bin/env bash
# Cria (uma vez) a pasta e os segredos de um ambiente não-produção: dev ou stag.
# Idempotente: não sobrescreve segredo que já existe.
#   bash deploy/nonprod/init-env.sh dev
set -euo pipefail
ENV_NAME="${1:?uso: init-env.sh dev|stag}"
case "$ENV_NAME" in dev|stag) ;; *) echo "env inválido: $ENV_NAME" >&2; exit 2 ;; esac
BASE="/data/bestmodel/nonprod/$ENV_NAME"
umask 077
mkdir -p "$BASE/postgres"
chmod 700 "$BASE"

secret() { openssl rand -hex 24; }
put() { # put FILE KEY VALUE — só grava se a chave ainda não existe
  local file=$1 key=$2 value=$3
  touch "$file"; chmod 600 "$file"
  command grep -q "^${key}=" "$file" || printf '%s=%s\n' "$key" "$value" >> "$file"
}

C="$BASE/compose.env"
put "$C" BM_ENV "$ENV_NAME"
put "$C" POSTGRES_USER bestmodel
put "$C" POSTGRES_PASSWORD "$(secret)"
put "$C" POSTGRES_DB "bestmodel_${ENV_NAME}"
# Domínios PROPOSTOS (a publicar só quando o Carlos criar DNS/túnel — ação dele):
put "$C" API_DOMAIN "api-${ENV_NAME}.bestmodel.run"
put "$C" AUTH_EXPECTED_ORIGIN "https://api-${ENV_NAME}.bestmodel.run"
put "$C" AUTH_RP_ID "bestmodel.run"
put "$C" CORS_ORIGINS "https://api-${ENV_NAME}.bestmodel.run"
# OAuth de terceiros FALSO no nonprod (par vazio = 503 "not configured", sem risco)
put "$C" GITHUB_CLIENT_ID "fake-${ENV_NAME}"
put "$C" GITHUB_CLIENT_SECRET "fake-${ENV_NAME}"
put "$C" HUGGINGFACE_CLIENT_ID "fake-${ENV_NAME}"
put "$C" HUGGINGFACE_CLIENT_SECRET "fake-${ENV_NAME}"
put "$C" PUBLIC_API_BASE "https://api-${ENV_NAME}.bestmodel.run"
put "$C" MODERATOR_HANDLES "carl0sfelipe"

# Senha do portão (basic auth). Texto claro só neste arquivo (600).
G="$BASE/gate-password"
[ -s "$G" ] || { openssl rand -base64 18 | tr -d '/+=' | cut -c1-20 > "$G"; chmod 600 "$G"; }

# Caddyfile do portão: basic auth em tudo + noindex. Sem auto_https (sem porta publicada).
CF="$BASE/Caddyfile"
if [ ! -s "$CF" ]; then
  HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext "$(cat "$G")")
  cat > "$CF" <<EOF
{
	admin off
	auto_https off
	servers {
		trusted_proxies static private_ranges
	}
}
:80 {
	header X-Robots-Tag "noindex, nofollow"
	basic_auth {
		orbe ${HASH}
	}
	reverse_proxy api:8000
}
EOF
  chmod 644 "$CF"
fi

echo "ok: $BASE"
