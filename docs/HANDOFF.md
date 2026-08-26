# bestmodel.run — Handoff Document

> **Data:** 2026-08-25 · **Autor:** sessão de engenharia (Claude Code) · **Repo:** [carl0sfelipe/bestmodel](https://github.com/carl0sfelipe/bestmodel) (público) + [carl0sfelipe/bestmodel-cloud](https://github.com/carl0sfelipe/bestmodel-cloud) (privado)
>
> Objetivo deste documento: permitir continuar o projeto em outra máquina/sessão com contexto zero. Tudo o que está no git está atualizado e testado; este arquivo documenta o que **não** está no código: decisões, estado de produção, segredos, passos manuais pendentes e a ordem recomendada de continuação.

---

## 1. O produto

**bestmodel.run** é a rede social open source de performance de IA local. Pergunta central: *"sua máquina roda qual modelo, a quantos tok/s?"* — respondida com dados medidos e assinados, não fórmulas.

O flywheel (mecânica central, chamada de **settle flow**):

1. Alguém posta uma **claim** (afirmação sem prova): *"Rodei Qwen 7B a 18.7 tok/s na minha 3090"* → status `open`, badge `UNVERIFIED`
2. A **comunidade vota** plausível/impossible (peso do voto escala com reputação L0=0.2 … L4=1.0)
3. **Settle** = provar com run assinada: o dono roda o CLI com `--settle-claim <id>`; o worker anti-fraude valida (evidência, plausibilidade física roofline, outliers); só aí vira `settled_verified` e credita reputação (+25 base, +15 bônus se a comunidade tinha votado impossível)
4. Claims **nunca** entram no leaderboard — só run assinada e validada entra

Princípio inegociável: **honestidade de números** (`measured > reported > extrapolated > formula > no data yet`). Número inventado é bug crítico.

O lado comercial (fechado): `bestmodel-cloud` — inferência gerenciada alugando GPU de provedores, containers otimizados, revenda por token. Ainda **não implementado**; a fronteira de integração está definida na spec L02 e no runbook de deploy (HTTP público só, nada compartilhado).

## 2. Estado atual (o que existe e funciona)

### Repos

| Repo | Conteúdo |
|---|---|
| `carl0sfelipe/bestmodel` (público, AGPL+MIT) | Monorepo: engine de compatibilidade, API social completa, CLI Rust, site, console, infra |
| `carl0sfelipe/bestmodel-cloud` (privado) | Só esqueleto README com escopo/contrato — código nenhum |

### Stories entregues (todas commitadas e pushed)

| Story | Commit | O quê |
|---|---|---|
| S13 | `4ca690a` | Auth passkey-first (WebAuthn/py_webauthn 2.8) + agent tokens (SHA-256 at rest) |
| S14 | `7911b60` | Rigs, perfis públicos, binding ao catálogo |
| S15 | `44d6890` | Claims com priors congelados + votação ponderada (property-tested) |
| S16 | `9f945aa` | Settle flow (upload autenticado vincula claim↔run; worker completa settlement + reputação) |
| S17 | `04a7baa` | Follows, notificações, feed tipado |
| S18 | `0303951` | Cards compartilháveis SVG+markdown (golden-file gate) |
| S19 | `9426bca` | Console web sem terminal (`apps/web/console`, oracle node:test 5/5) |
| S20 | `8a118b8` | Badges embutíveis + rate limits por reputação (claims 2–50/24h, votos 5–250/h) |
| CLI B4 | `5f38e74` | `--settle-claim` no benchmark-probe + `BENCHMARK_PROBE_API_TOKEN` |
| Deploy | `5ebb77d` | Vercel front + Docker backend portátil (Caddy edge OU Cloudflare tunnel) |
| S22 | `083b29e` | Import localmaxxing (551 claims em prod) + expansão de catálogo via HF |

### Verificação

- `make test` → **233 passed**
- `cargo test --workspace` → **20 passed**
- `node apps/web/scripts/check-console.mjs` → **5/5**
- `make gate` → **PASS** (gate e2e completo do repo, rodado em 2026-08-25)
- Postgres de dev (porta **5434**) e de produção (docker `bestmodel-prod`) com migrations **0001–0010** aplicadas

### 26 endpoints públicos (prefixo /v1)

`auth/passkey/*` (4) · `auth/tokens` (3) · `rigs` (4) · `users/{handle}` (1) · `users/{handle}/follow` (2) · `claims` (5) · `cards/claims/{id}.svg|.md` (2) · `badges/runs/{id}.svg` (1) · `feed` · `notifications` (2) · `submissions` (2) · `match` (2) · `leaderboard` (1) — detalhes em `llms.txt` e no OpenAPI (`/docs` da API).

## 3. Arquitetura e topologia de deploy

```
bestmodel.run (Vercel: apps/web/site + /console)
    └─ vercel.json reescreve /v1/* → https://api.bestmodel.run
           └─ [edge: Caddy auto-TLS OU Cloudflare Tunnel — tunnel é o plano vigente]
                  └─ beelink (docker compose "bestmodel-prod"):
                        api (uvicorn) · worker (intake) · postgres(timescale+vector) · redis
                        estado 100% em volumes nomeados
```

- Compose de produção: `deploy/docker-compose.prod.yml` (perfis `edge`/`tunnel`)
- Imagem única api+worker: `infra/docker/api.Dockerfile` (uv frozen, migrations embutidas)
- Migração pra outra cloud = `pg_dump` + rsync volumes + flip DNS (checklist em `docs/en/deploy.md`)
- Portas de **dev** no beelink (convenção do repo, NÃO mudar): postgres **5434**, redis **6380**, minio 9002/9003, meilisearch 7701 — as portas default pertencem a outro stack de produção colocalizado (Orbe)

### Estado de produção AGORA (beelink)

- Stack `bestmodel-prod` rodando e healthy: postgres, redis, api, worker (Caddy foi removido — sem acesso ao roteador)
- **551 claims importadas** do localmaxxing (37 modelos, 252 roofline priors) — o feed nasce populado
- Catálogo: **76 modelos / 29 GPUs**
- Semana HTTP externa ainda — depende dos passos manuais (seção 5)

## 4. Segredos e chaves (ONDE ESTÃO — nada disso está no git)

| Segredo | Local no beelink | Nota |
|---|---|---|
| Senha forte do Postgres prod | `~/Work/bestmodel/deploy/.env` (`POSTGRES_PASSWORD`) | gitignored |
| Chave privada Ed25519 (assina benchmarks aceitos pelo intake) | `~/secrets-bestmodel/gate-key.pem` **e** `~/.config/benchmark-probe/ed25519.pem` | Quem tem essa chave publica runs validadas — o modelo de confiança atual é single-signer (limitação conhecida, ver seção 8) |
| Chave pública confiável (montada no container) | `deploy/secrets/trusted_public.pem` | bind-mount ro no compose |
| `TUNNEL_TOKEN` | ainda não existe | você cria no painel da Cloudflare (passo B2) |

O par de chaves foi gerado em `/tmp` primeiro e **copiado** para os locais persistentes — os arquivos em `~/secrets-bestmodel/` são os canônicos.

## 5. Passos manuais pendentes (o lançamento trava aqui)

Você (dono) precisa fazer, nesta ordem:

**B1 — Cloudflare** (~10 min + propagação)
1. Conta em dash.cloudflare.com (Free)
2. Add domain `bestmodel.run` → plano Free → importar registros sugeridos
3. Trocar os nameservers no registrador pelos 2 que a CF mostrar
4. Aguardar e-mail "active"

**B2 — Tunnel** (após B1)
1. one.dash.cloudflare.com → Networks → Tunnels → Create (Cloudflared) → nome `beelink`
2. Copiar o token → adicionar `TUNNEL_TOKEN=eyJ...` em `deploy/.env` (não colar em chat)
3. Public Hostname: subdomain `api` · domain `bestmodel.run` · Service `HTTP api:8000`

**B3 — DNS pra Vercel** (no painel DNS da CF)
- `A @ 76.76.21.21` (DNS only, nuvem cinza)
- `CNAME www cname.vercel-dns.com` (DNS only)

**B4 — Vercel**
1. vercel.com/new → importar `carl0sfelipe/bestmodel` → Root Directory **`apps/web`** → Framework Other (vercel.json cuida do resto)
2. Settings → Domains → adicionar `bestmodel.run` e `www.bestmodel.run`

**Depois me chamar pra:** `docker compose -f deploy/docker-compose.prod.yml --profile tunnel --env-file deploy/.env up -d cloudflared` + bateria de verificação (nonce via domínio, console cria conta passkey, claim, voto, card, badge) + instalar cron de backup (`deploy/scripts/backup-db.sh`, exemplo de cron no runbook).

## 6. Decisões tomadas (e por quê — não refazer sem motivo)

1. **Licença híbrida**: AGPL-3.0 em `apps/**` (protege o SaaS), MIT em `packages/**`+`cli/**` (adoção viral do engine)
2. **Histórico limpo**: repo público nasceu de commit único — investor-brief, planos chineses e mapa de portas ficaram só no CanIRunIt privado
3. **PNG dos cards adiado**: SVG puro (zero deps, política do pack web); rasterização fica pra client/proxy
4. **Settle exige auth do dono** — run anônima não settle claim de ninguém; duelos entre contas ficaram fora (C2 aberto)
5. **Import localmaxxing** (dono liberou, open source, "é só claim"): só track claimed, nunca leaderboard; granularidade por célula; células flagged impossible descartadas (via derive já limpo); autor visível "localmaxxing pool"; atribuição em note/README/User-Agent
6. **Expansão de catálogo sem inventar**: specs vêm do `config.json` da HF + safetensors; `active_parameter_count` anulado onde a HF não declara; GPUs novas só com bandwidth oficial; Arc B70/R9700/M5 ficaram fora por falta de número confirmável
7. **Plano B (tunnel)** vigente porque não há acesso ao roteador; IP público real existe (177.130.86.138) e portas 80/443 do host estão livres — se um dia houver acesso ao roteador, o perfil `edge` (Caddy) é um `up -d --profile edge`
8. **Trust model single-signer**: o intake aceita apenas runs assinadas pela chave do dono (`TRUSTED_ED25519_PUBLIC_KEY_PATH`) — limitação herdada do Phase 0, ver seção 8

## 7. Convenções do repo (obedecer cegamente)

- **AGENTS.md por diretório** — o mais próximo do edit vence; ler o raiz antes de qualquer coisa
- Commits: `feat(S13): ...` convencionais, inglês; **um commit por story**
- Python via `uv` (`uv sync`, `uv run pytest`); testes: `make test` é a entrada única; gate e2e: `make gate`
- **FakeDatabase em lockstep**: todo método novo no `DatabaseSession` (ABC em `apps/public-api/src/dependencies/database_session_provider.py`) ganha implementação no `packages/fake-adapters/src/fake_database.py` **no mesmo commit**
- Wrappers finos de py_webauthn são patch-points de teste (`_generate_registration_options` etc.) — `make_passkey_session` no conftest usa isso
- Migrations append-only (0001–0010 existem); nunca editar aplicada
- Specs executáveis em `specs/en/` com acceptance por story; status da L02 atualizado story a story
- Código/doc novo em inglês; specs PT históricas congeladas
- Rust: binários caem em `./target/debug/` do raiz
-uv venv é path-bound: após mover o repo, `rm -rf .venv && uv sync`

## 8. Dívida técnica e próximos passos (ordem recomendada)

1. **Lançar** (seção 5 — só depende de você)
2. **Per-user signing keys** (substituir single-signer): registar chave pública Ed25519 por conta (o CLI já tem par de chaves local); worker valida contra a chave do dono da run. É pré-requisito de escala real do settle flow
3. **Duelos C2**: challenger anexa run validada própria a claim alheia; crédito pros dois lados; notificação `duel_result` (kind já existe no schema)
4. **L01 — CLI v2 Local Lab** (`specs/en/L01-cli-v2-local-lab.md`): `plan`/`lab`/`report`/`contribute` — decisões A1–A6 do backlog ainda abertas
5. **Backlog de catálogo**: 411 células em fine-tunes de cauda (o importador reporta o top); 348 células multigpu (precisa gpu_count no claim); novos rigs sem spec confirmada
6. **bestmodel-cloud** (repo privado): gateway OpenAI-compatible, orchestrator multi-provider, imagens otimizadas, metering/billing — validar ToS de revenda (Vast.ai/RunPod) ANTES de construir margem em cima
7. Track D (difusão/ComfyUI) lado plataforma: D1–D4 no backlog
8. Cron de backup pós-launch (comando no runbook §Backups)

## 9. Mapa rápido do monorepo

```
apps/public-api      API FastAPI (26 endpoints) — services/ flat modules, rotas por recurso
apps/intake-worker   worker anti-fraude (queue Redis stream "benchmark_runs")
apps/web             site estático + console/ (S19) + vercel.json + data/derived/pool.json
apps/pool-backend    sync localmaxxing→SQLite + plausibility roofline (pré-existente, reutilizado)
packages/            roofline-kernel, domain-schema, runtime-probes, recommendation-engine, fake-adapters (MIT)
cli/benchmark-probe  Rust: detecta hardware, roda cenário, assina (Ed25519), upload; --settle-claim
cli/comfy-lab        vertical difusão (ComfyUI probe)
infra/               docker, migrations 0001–0010, seed (76 modelos/29 GPUs), scripts (import/expand/gate)
deploy/              compose prod, Caddyfile, env.example, scripts de backup/restore
specs/en/            L01 (planned), L02 (S13–S20 done) — fonte de verdade dos stories
docs/en/             deploy.md (runbook), plan/architecture/findings/backlog no nível acima
```

## 10. Ambiente da máquina (beelink)

- Linux; `uv` via mise (`~/.local/share/mise/shims`), Rust via `~/.cargo/bin` (rustup instalado na sessão), Docker + compose presentes
- `make test` requer `uv` no PATH: `export PATH="$HOME/.local/share/mise/shims:$PATH"`
- Clones: `~/Work/bestmodel` (público) · `~/Work/bestmodel-cloud` (privado) · `~/Work/CanIRunIt` (repo histórico privado de onde o público foi derivado)
- Stack dev (5434) e prod (docker bestmodel-prod) coexistem; dev não tem porta exposta

## 11. Runbook de continuação (primeiros comandos em máquina nova)

```bash
git clone https://github.com/carl0sfelipe/bestmodel && cd bestmodel
export PATH="$HOME/.local/share/mise/shims:$HOME/.cargo/bin:$PATH"
uv sync
make check-ports && make infra-up && sleep 12   # dev: postgres 5434 + redis 6380
make migrate seed                               # schema 0001–0010 + catálogo
make test                                       # 233 green esperado
# produção (no beelink): deploy/.env + deploy/secrets/ já existem lá
```

Validações rápidas de sanidade: `make gate` (e2e completo), `uv run pytest apps/public-api/tests/test_settle_flow.py -q` (o coração do produto), `docker compose -f deploy/docker-compose.prod.yml ps` (saúde da prod).

---

*Última atualização deste documento: pós-S22 (`083b29e`), 233 testes verdes, 551 claims em produção.*
