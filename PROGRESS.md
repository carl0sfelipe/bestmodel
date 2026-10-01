# PROGRESS — bestmodel dev/stag/prod (spec: ~/Work/specs-dev-stag/bestmodel-dev-stag-prod.md)

## Log

- 2026-10-01 19:05 -03 — STEP 0 (só leitura, ~10 min). Executor: zcode/GLM-5.3 (spec, tentativa 1).
  Uptime dos 6 containers de prod no início (prod NÃO tocado):
  bestmodel-prod-worker-1/api-1/postgres-1 Up 42 hours (healthy); bestmodel-prod-caddy-1/cloudflared-1/redis-1 Up 3 days (healthy onde aplicável).
  - Repo de prod: ~/Work/bestmodel, branch main, HEAD 65e512f. Compose: deploy/docker-compose.prod.yml (name: bestmodel-prod)
    + deploy/docker-compose.omarchy.yml (postgres em /data/bestmodel/postgres, timescaledb com PGDATA forçado;
    cloudflared via ~/.cloudflared local, NÃO via TUNNEL_TOKEN).
  - Serviços: postgres (infra/docker/postgres.Dockerfile), redis, api (infra/docker/api.Dockerfile, uvicorn :8000,
    HEALTHCHECK em /v1/submissions/nonce), worker (mesma imagem, consome stream redis `benchmark_runs` via consumer
    group e publica em `ranking_updates`), caddy (profile edge, 80/443, {$API_DOMAIN}→api:8000), cloudflared (profile tunnel).
  - Rotas confirmadas no código: GET /v1/health (devolve git_sha/built_at do build arg), GET /v1/leaderboard,
    GET /v1/model-releases, POST /v1/match/hardware-to-models. Healthcheck da imagem: /v1/submissions/nonce.
  - Migrações: infra/migrations/ (18 arquivos .sql lexicográficos); infra/scripts/migrate.py (idempotente,
    grava em meta.schema_migrations) e infra/seed/ JÁ VÊM NA IMAGEM (/app/infra/...).
  - deploy/.env (SÓ nomes): POSTGRES_USER/PASSWORD/DB, API_DOMAIN, AUTH_EXPECTED_ORIGIN, AUTH_RP_ID, CORS_ORIGINS,
    GITHUB_CLIENT_ID/SECRET, HUGGINGFACE_CLIENT_ID/SECRET, PUBLIC_API_BASE, MODERATOR_HANDLES.
  - Segredo de assinatura: deploy/secrets/trusted_public.pem (montado ro em api e worker — chave PÚBLICA).
  - Backup existente: ~/Work/bestmodel-backups/bestmodel.sql (+artifacts.tar.gz). backup-db.sh faz dump via docker exec.
  - Front: apps/web e apps/web-next existem; qual está na Vercel ficou [A DEFINIR com o Carlos] (não bloqueia o API-only desta spec).
  - Portas do host ocupadas: 80, 443, 5433, 5436 (nonprod não publica porta nenhuma, como no orbe).
- 2026-10-01 19:05 -03 — Plano de execução (espelha o que funcionou no orbe, lições aplicadas: smoke com retry,
  mesma imagem dev=stag via retag, sem seed fantasma): branch feat/dev-stag; nonprod compose overlay + init-env + restore-db
  (dump FRESCO de prod via docker exec — leitura — e anonimização dinâmica por nome de coluna); portão Caddy com basic auth
  + noindex; flow-bestmodel.sh (health, migrações, worker consome evento sintético, leaderboard com dados); promote-prod.sh
  com --dry-run padrão (nesta spec só o dry-run roda).
