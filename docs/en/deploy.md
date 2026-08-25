# Production deployment & migration runbook

Topology: **static site + console on Vercel**, **stateful backend on Docker
(any host — currently the beelink)**. The split is deliberately boring: the
frontend is a pure static artifact, and every durable byte on the backend
lives in a named volume or a bind mount, so moving clouds is data transfer +
DNS flip, not re-engineering.

```text
browser ──> bestmodel.run (Vercel: site + console)
                │  /v1/* rewritten (vercel.json) ── no CORS needed in practice
                ▼
        api.bestmodel.run (Caddy TLS or Cloudflare Tunnel)
                │
        beelink docker: api · worker · postgres · redis   ← state lives here
```

## First deploy

1. **Secrets**
   ```bash
   cp deploy/env.example deploy/.env       # then edit credentials/domains
   mkdir -p deploy/secrets
   # Ed25519 trusted key: the PUBLIC half verifies CLI signatures at intake.
   # Generate once; keep the private half wherever the gate/CLI signs.
   openssl genpkey -algorithm ed25519 -out /tmp/gate-key.pem
   openssl pkey -in /tmp/gate-key.pem -pubout -out deploy/secrets/trusted_public.pem
   chmod 600 deploy/.env deploy/secrets/*
   ```
2. **Edge** — pick one profile:
   - `--profile edge` (Caddy): DNS `A/AAAA api.bestmodel.run -> this host`,
     ports 80/443 open. Certificates are automatic.
   - `--profile tunnel` (cloudflared): no open ports. Create the tunnel in
     Cloudflare Zero Trust, set `TUNNEL_TOKEN`, route its hostname to
     `http://api:8000`.
3. **Up**
   ```bash
   docker compose -f deploy/docker-compose.prod.yml --profile edge --env-file deploy/.env up -d --build
   docker compose -f deploy/docker-compose.prod.yml exec -T api \
     sh -c "cd /app && uv run python infra/scripts/migrate.py && uv run python infra/scripts/seed/load_seed.py"
   ```
4. **Frontend** — import `apps/web/` on Vercel (framework: Other). `vercel.json`
   publishes `site/` + `console/` and proxies `/v1/*` to
   `api.bestmodel.run`. Point the domain, done.

The console talks same-origin (`config.js` sets an empty base); passkeys and
the honesty ladder work unchanged.

## Backups (do this before anything else)

```bash
chmod +x deploy/scripts/*.sh
deploy/scripts/backup-db.sh          # also wire it into cron:
# 10 4 * * * /srv/bestmodel/deploy/scripts/backup-db.sh >> /srv/bestmodel/backups/backup.log 2>&1
```

Artifacts (benchmark evidence files) live in the `artifacts` volume — back up
that directory with any file sync tool; they are immutable once written.

## Migrating to another cloud

Nothing in the stack knows where it runs (all config via env; no hostnames
baked into images):

1. On the new host: clone repo, copy `deploy/.env` + `deploy/secrets/`
2. Restore data:
   ```bash
   docker compose -f deploy/docker-compose.prod.yml up -d postgres redis
   cat backup.sql.gz | gunzip | docker compose -f deploy/docker-compose.prod.yml exec -T postgres \
     psql -U bestmodel -d bestmodel
   rsync -a old:/var/lib/docker/volumes/bestmodel-prod_artifacts/ volumes artifacts equivalent
   ```
3. `up -d` the rest, flip DNS (`api.bestmodel.run` + Vercel rewrite target).
4. Old host: `down`. Total downtime = DNS TTL + container start.

Scale-up path later: the compose services map 1:1 to containers on a single
bigger VM first (same volumes), and only after that to managed Postgres /
k8s — the app never needs code changes for either step.

## Integrating the closed-source inference side (bestmodel-cloud)

Boundary rules already enforced by L02 stay true in production:

- The proprietary gateway joins as **another compose service**
  (`profiles: ["cloud"]`) behind the same Caddy/tunnel with its own
  hostname (e.g. `gw.bestmodel.run`). It shares **nothing** with this stack:
  own database if it wants one, own secrets, own image registry.
- Integration is HTTP only: the open platform's opt-in `cloud` module calls
  the gateway's public API; the gateway may read the **public** API like any
  client. No shared tables, no shared Redis logical DB (use separate
  instance or distinct DB indexes).
- Anything the closed side needs from the open platform must flow through
  documented public endpoints — that keeps both sides independently
  migratable, which is the whole point of this layout.
