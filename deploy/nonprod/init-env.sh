#!/usr/bin/env bash
# Cria (uma vez) a pasta e os segredos de um ambiente não-produção: dev ou stag.
# Idempotente: não sobrescreve segredo que já existe.
#   bash deploy/nonprod/init-env.sh dev
set -euo pipefail
ENV_NAME="${1:?uso: init-env.sh dev|stag}"
case "$ENV_NAME" in dev|stag) ;; *) echo "env inválido: $ENV_NAME" >&2; exit 2 ;; esac
# BM_DATA_ROOT lets offline tests run the script against a scratch root.
BASE="${BM_DATA_ROOT:-/data/bestmodel}/nonprod/$ENV_NAME"
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
put "$C" WEB_DOMAIN "${ENV_NAME}.bestmodel.run"
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

# Gate Caddyfile: basic auth on everything + noindex, no auto_https (no
# published port). Routing: /v1/* -> api:8000, everything else -> web:3000.
# Never overwrites an existing file; if one exists, prints a diff hint instead.
CF="$BASE/Caddyfile"
render_caddyfile() { # $1 = pre-hashed basic_auth password
  cat <<EOF
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
		orbe $1
	}
	handle /v1/* {
		reverse_proxy api:8000
	}
	handle {
		reverse_proxy web:3000
	}
}
EOF
}
gate_hash() { # bcrypt-hash the plaintext gate password the way caddy expects
  docker run --rm caddy:2-alpine caddy hash-password --plaintext "$1" 2>/dev/null || true
}
if [ ! -s "$CF" ]; then
  HASH="$(gate_hash "$(cat "$G")")"
  [ -n "$HASH" ] || { echo "error: could not hash the gate password (docker/caddy:2-alpine unavailable?)" >&2; exit 1; }
  render_caddyfile "$HASH" > "$CF"
  chmod 644 "$CF"
else
  echo "note: $CF already exists; it will not be overwritten."
  HASH="$(gate_hash "$(cat "$G")")"
  if [ -n "$HASH" ]; then
    # The basic_auth hash carries a random salt, so compare with that line
    # normalized; every other difference is a real divergence.
    TPL="$(mktemp)"
    render_caddyfile "$HASH" | sed 's/orbe \$2a[^ ]*/orbe <hashed>/' > "$TPL"
    NORM="$(mktemp)"
    sed 's/orbe \$2a[^ ]*/orbe <hashed>/' "$CF" > "$NORM"
    if diff -u "$NORM" "$TPL" >/dev/null; then
      echo "note: $CF matches the current template (hash line re-salted on each render)."
    else
      echo "hint: $CF differs from the current template (diff below, hash line normalized):"
      diff -u "$NORM" "$TPL" || true
    fi
    rm -f "$TPL" "$NORM"
  else
    echo "hint: could not render the template (docker/caddy:2-alpine unavailable); remove $CF and re-run to regenerate."
  fi
fi

echo "ok: $BASE"
