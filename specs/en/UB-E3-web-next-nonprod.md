# Task: web-next on bestmodel dev (live) and stag (built image)

OBJETIVO: the bestmodel nonprod stack serves only the API today. Add the web-next site so the AI edits on `dev.bestmodel.run` (live `next dev`, edits visible in seconds) and the owner tests on `stag.bestmodel.run` (built image of a commit), behind the existing password gate. Write files only; never run docker, never touch DNS, Cloudflare, Vercel or prod.

## Dados verificados
- `deploy/docker-compose.nonprod.yml` overrides `deploy/docker-compose.prod.yml` for `-p bestmodel-dev|bestmodel-stag`; it has `postgres`, `api`, `worker`, `gate` (caddy, Caddyfile at `/data/bestmodel/nonprod/${BM_ENV}/Caddyfile`); `caddy` and `cloudflared` are disabled by profile.
- `deploy/nonprod/init-env.sh dev|stag` creates `/data/bestmodel/nonprod/<env>/compose.env` and secrets, idempotent.
- `apps/web-next` is Next 15 (`next dev`, `next build`, `next start`); prod web is on Vercel; there is no web-next Dockerfile. `next.config.ts` traces `../docs/agent-quickstart.md` and the repo-root intent catalog, and rewrites `/v1/*` to `API_ORIGIN` when set.
- Node tests: `cd apps/web-next && node --experimental-strip-types --test lib/*.test.ts`.

Nao invente numero, prazo ou fonte alem dos listados.
NUNCA use declare const como workaround — importe de verdade.

## PROIBIDO
Running docker/cloudflared/systemctl. DNS. push. Editing `deploy/docker-compose.prod.yml`, Vercel config, `apps/web-next` source code. Secrets in git. Portuguese in new code/comments/messages.

## PASSOS
1. `infra/docker/web-next.Dockerfile` with build context = repo root:
   - stage `deps`: node:22-alpine, copies `apps/web-next/package.json` + lockfile, `npm ci`.
   - stage `devlive`: from deps, workdir `/repo/apps/web-next`, `CMD npx next dev -H 0.0.0.0 -p 3000` (source arrives by bind mount).
   - stage `builder`: copies the files next.config.ts traces (`apps/web-next`, `docs/agent-quickstart.md`, the intent catalog path used by the app — find it in `apps/web-next/lib` imports), runs `next build`.
   - stage `runner`: `next start -p 3000`, non-root user, `LABEL org.opencontainers.image.revision=$REVISION`.
2. `deploy/docker-compose.nonprod.yml`: add service `web` (target `runner`, env `API_ORIGIN=http://api:8000`, healthcheck `wget -q -O /dev/null http://127.0.0.1:3000/llms.txt`). The gate keeps routing: `/v1/*` → `api:8000`, everything else → `web:3000` (update the Caddyfile template, see step 4).
3. `deploy/docker-compose.devlive.yml`: overlay for dev only; `web` built from target `devlive`, repo bind-mounted at `/repo` read-only except `apps/web-next/.next` (anonymous volume) and `node_modules` (anonymous volume so the image install wins).
4. `deploy/nonprod/init-env.sh`: also write the gate Caddyfile when missing (never overwrite an existing one; print a diff hint instead) with `basic_auth`, `X-Robots-Tag "noindex, nofollow"`, `handle /v1/*` → api, default → web. Add `WEB_DOMAIN=<env>.bestmodel.run` to compose.env.
5. `deploy/nonprod/dev-live.sh up|logs|image` and `deploy/nonprod/ship.sh dev|stag [--all]`: same behavior as described for Orbe-style flow: dev-live builds+recreates `web` with the overlay and waits for health; ship refuses uncommitted changes under `apps/ packages/ infra/ deploy/`, builds `web` (and `api`/`worker` when their paths changed since the running image's revision label), recreates, then smoke.
6. `deploy/nonprod/smoke.mjs <dev|stag>`: Node 22 fetch only, gate auth from `/data/bestmodel/nonprod/<env>/gate-password` or `GATE_PASSWORD`, `BASE_URL` override. Checks: `/` 200, `/llms.txt` 200 containing `bestmodel.run`, `/wall?as=agent` 200 containing `Honesty ladder`, `/v1/leaderboard` 200 JSON with `runs`, `X-Robots-Tag` present.
7. `deploy/nonprod/test.sh`: offline: `bash -n` scripts, `node --check smoke.mjs`, init-env into a temp root (`BM_DATA_ROOT` override — add it) creates Caddyfile with both handles and does not overwrite on 2nd run; `docker compose config -q` for dev+devlive and stag only if docker exists; prod compose unchanged vs HEAD.

VERIFICACAO: bash deploy/nonprod/test.sh && grep -q "AS devlive" infra/docker/web-next.Dockerfile && grep -q "handle /v1" deploy/nonprod/init-env.sh

## Oraculo
- comando: test -f deploy/nonprod/test.sh && bash deploy/nonprod/test.sh && grep -q "AS devlive" infra/docker/web-next.Dockerfile && git diff --quiet HEAD -- deploy/docker-compose.prod.yml
- exit esperado: 0

## Barra
- nome: deploy/nonprod/test.sh
- como fetchar: bash deploy/nonprod/test.sh
- como comparar: offline self-tests green, prod compose untouched
