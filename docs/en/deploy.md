# Production deployment & migration runbook

> Supersedes the 2026-08 version of this file (it described a static site on
> Vercel plus a beelink host; neither is the topology any more). Verified
> against the running stack on 2026-11-12.

Topology: **Next.js front on Vercel** (`apps/web-next`, deployed from `main`
by the GitHub integration), **stateful backend on Docker** on the omarchy
host. Every durable byte on the backend lives in a named volume or a bind
mount, so moving hosts is data transfer + DNS flip, not re-engineering.

```text
browser ──> www.bestmodel.run (Vercel: apps/web-next)
                │  NEXT_PUBLIC_API_BASE=https://api.bestmodel.run
                ▼
        api.bestmodel.run (Caddy TLS or Cloudflare Tunnel)
                │
        docker (omarchy): api · worker · postgres · redis   ← state lives here
```

The front calls the API cross-origin, so `CORS_ORIGINS` in `deploy/.env`
must name every host the front is served from (`https://www.bestmodel.run`,
`https://bestmodel.run`, the Vercel preview domain). The API is
cookie-less: auth is `Authorization: Bearer` from `localStorage`, so there
is no CSRF surface and no session cookie to steal.

## What lives where

| Thing | Where | Note |
|---|---|---|
| Front | Vercel, from `main` | `apps/web-next`; `NEXT_PUBLIC_API_BASE` is a Vercel env var |
| API + worker | `deploy/docker-compose.prod.yml` (+ `docker-compose.omarchy.yml`) | project name `bestmodel-prod` |
| Postgres | named volume, PGDATA forced to a bind mount by the omarchy override | timescaledb |
| Redis | named volume | stream `benchmark_runs`, consumer group for the worker |
| Ed25519 trusted key | `deploy/secrets/trusted_public.pem` (public half, mounted read-only) | the private half never touches this host |
| Backups | `deploy/scripts/backup-db.sh` → `BACKUP_DIR` | nightly logical dump |

## First deploy

1. **Secrets**
   ```bash
   cp deploy/env.example deploy/.env       # then edit credentials/domains
   mkdir -p deploy/secrets
   openssl genpkey -algorithm ed25519 -out /tmp/gate-key.pem
   openssl pkey -in /tmp/gate-key.pem -pubout -out deploy/secrets/trusted_public.pem
   chmod 600 deploy/.env deploy/secrets/*
   ```
   `AUTH_EXPECTED_ORIGIN` is a **comma-separated list** of the origins a
   passkey ceremony may come from — the site answers on the apex and on
   `www`, and the browser sends the origin of the page it is on. A single
   value silently breaks sign-in on the other host.
2. **Edge** — pick one profile:
   - `--profile edge` (Caddy): DNS `A/AAAA api.bestmodel.run -> this host`,
     ports 80/443 open. Certificates are automatic.
   - `--profile tunnel` (cloudflared): no open ports. The tunnel lives in
     `~/.cloudflared` on the host; the compose profile expects `TUNNEL_TOKEN`.
3. **Up**
   ```bash
   eval "$(deploy/build-args.sh)"   # bakes the real git_sha into /v1/health
   docker compose -p bestmodel-prod \
     -f deploy/docker-compose.prod.yml -f deploy/docker-compose.omarchy.yml \
     --env-file deploy/.env up -d --build
   ```

## The safe path: dev → stag → prod

Never rebuild in prod. The image that passes in stag is the image that goes
up, retagged — never rebuilt.

```bash
# 1. dev (same host, own project name, no published ports, own secrets)
bash deploy/nonprod/init-env.sh dev
eval "$(deploy/build-args.sh)"
BM_ENV=dev docker compose -p bestmodel-dev \
  -f deploy/docker-compose.prod.yml -f deploy/docker-compose.nonprod.yml \
  --env-file /data/bestmodel/nonprod/dev/compose.env up -d --build
bash deploy/nonprod/restore-db.sh dev      # fresh dump of prod, anonymized
bash infra/scripts/flow-bestmodel.sh dev   # health, migrations, worker, leaderboard

# 2. stag: the SAME image, retagged
docker tag bestmodel-dev-api:latest bestmodel-stag-api:latest
BM_ENV=stag docker compose -p bestmodel-stag \
  -f deploy/docker-compose.prod.yml -f deploy/docker-compose.nonprod.yml \
  --env-file /data/bestmodel/nonprod/stag/compose.env up -d
bash deploy/nonprod/restore-db.sh stag
bash infra/scripts/flow-bestmodel.sh stag

# 3. prod: dry-run first, then --apply
bash deploy/promote-prod.sh
BM_PROMOTE_ALLOW=yes bash deploy/promote-prod.sh --apply
```

`promote-prod.sh --apply` does, in this order: **backup-db → tag the running
image as `rollback-<stamp>` → run the migrations with a one-off container on
the new image (the API that is up keeps serving) → swap the api and worker
→ smoke `/v1/health` six times.** Rollback is one command:

```bash
docker tag bestmodel-prod-api:rollback-<stamp> bestmodel-prod-api:latest
docker compose -p bestmodel-prod \
  -f deploy/docker-compose.prod.yml -f deploy/docker-compose.omarchy.yml \
  --env-file deploy/.env up -d --no-build api worker
```

Migrations are append-only. A migration that a previous release cannot
survive is a rollback that needs a down-migration — write them that way.

## The front

The front deploys from `main` (Vercel Git integration). The order matters:
**promote the API first, then merge the front**, because a front that calls
an endpoint the running API does not have yet answers "not signed in" to
everybody.

Before merging, the front must be green locally:

```bash
cd apps/web-next
npm ci
npm test
node scripts/check-snapshot.mjs   # stats.json against the files beside it
npm run build
```

## Checks after a deploy

```bash
curl -s https://api.bestmodel.run/v1/health           # git_sha must be the new one
curl -s https://api.bestmodel.run/v1/leaderboard | head -c 120
curl -s -o /dev/null -w '%{http_code}\n' https://www.bestmodel.run/console
docker compose -p bestmodel-prod ... ps
```

`/v1/health` reports the `git_sha` baked into the image. If it does not
match the commit you deployed, the wrong image is running.

## What is NOT here

- Managed inference and any pricing: a separate, proprietary codebase. The
  open platform never requires it, and removing it must leave every social
  and engine feature working.
- One-line installer (`bestmodel.run/install.sh`): no install script is
  hosted yet, so the site must not render one.
