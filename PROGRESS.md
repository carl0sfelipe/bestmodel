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
- 2026-10-01 20:56 -03 — EXECUÇÃO CONCLUÍDA (commit adbc618, branch feat/dev-stag):
  - init-env dev/stag ok (segredos próprios 600, OAuth de terceiros FALSO).
  - Imagem dev buildada com git_sha 65e512f; RETAG para stag (mesma imagem conferida por image id).
  - restore-db nos dois: dump FRESCO de prod via docker exec (só leitura; 68K), 33 tabelas,
    anonimização dinâmica com contagens: auth_token.token_hash 2, contributor_account.email 1,
    contributor_account.token_hash 1 (dev e stag). Check de dump completo corrigido (timescaledb
    deixa linhas de comentário depois do "dump complete").
  - flow-bestmodel: **dev 4/4 e stag 4/4** (health com git_sha; migrações 17/17 — o "18" era
    AGENTS.md contado no ls, corrigido para contagem dinâmica de .sql; worker consumiu evento
    sintético pelo lag do consumer group; leaderboard JSON com dados reais).
  - promote-prod.sh --dry-run: PASSA (árvore limpa, dev==stag, flow stag verde, plano impresso).
    --apply exige BM_PROMOTE_ALLOW=yes (não rodou — prod é só leitura nesta spec).
  - PROD INTOCADO: uptimes no fim == STEP 0 (api/worker/postgres 43h, caddy/cloudflared/redis 3d).
  - Pendências/Ações do Carlos: DNS/túnel para api-dev/api-stag.bestmodel.run (dominíos propostos
    no compose.env); decidir se front dev/stag será Vercel preview apontando para as APIs nonprod
    [A DEFINIR]; quando quiser promover: BM_PROMOTE_ALLOW=yes bash deploy/promote-prod.sh --apply.
- 2026-10-01 18:56 -03 — HUNT autônoma (zcode/cursor-grok-4.6-xhigh-fast, branch feat/autonomous-bestmodel):
  - Baseline: bash infra/scripts/flow-bestmodel.sh dev → 4/4 (git_sha=65e512f).
  - Código sem TODO/FIXME em .py/.ts/.rs/.sh. e2e_gate.sh NÃO rodado: sobe infra/docker
    em 5434/6380 e pkill workers — stack diferente do projeto bestmodel-dev.
  - Front Vercel (só leitura): único vercel.json em apps/web (rewrite /v1 →
    https://api.bestmodel.run/v1); apps/web-next sem vercel.json no repo; POINTERS
    marca o README de apps/web como STALE e nomeia apps/web-next como front de prod.
    Qual projeto Vercel serve www.bestmodel.run permanece [A DEFINIR] (sem tocar deploy).
  - 3 commits verificados no bestmodel-dev (flow 4/4 após cada um; prod start times
    inalterados: api/worker/postgres 2026-09-30T02:13–02:14Z, caddy/cloudflared/redis
    2026-09-28T13:17Z):
    1. 0f4279b — POST /v1/match/model-to-hardware model-gemma-4-26b-a4b-it batch=2:
       500 → 200 (experts_per_token null * batch).
    2. 240833b — POST /v1/match/hardware-to-models gpu-gtx-1080-ti (e os outros 5 GPU
       com fp16_tflops null): 500 ZeroDivisionError no TTFT → 200 {"matches":[]}.
    3. 587fd14 — flow leaderboard também POST nesses dois buracos; ainda 4 passaram.
  - make test no host: 348 passed; 9 failed PermissionError em artifacts/ (ambiente,
    settle/social) — não introduzido por estes commits. Testes de match/prefill/decode: 44 passed.
