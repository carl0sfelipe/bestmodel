# Estado Omarchy — prod bestmodel.run (2026-09-18)

> Substitui o `HANDOFF.md` (beelink, 2026-08-25) como retrato do estado de
> produção. O beelink **morreu** (~2026-09-18, `api.bestmodel.run` 530/error
> 1033). A produção foi reinstalada no desktop **Omarchy** a partir do backup
> off-host de 2026-09-17T03:01Z.

## O que está rodando

Stack `bestmodel-prod` (Docker, daemon enabled no boot): **postgres, redis,
api, worker — todos healthy**. Caddy não é usado (plano tunnel, como no
beelink). Vercel segue servindo o site/console; Pages existe como preview.

```bash
cd ~/Work/bestmodel
docker compose -f deploy/docker-compose.prod.yml -f deploy/docker-compose.omarchy.yml \
  --env-file deploy/.env up -d        # "--profile tunnel" quando houver TUNNEL_TOKEN
```

## Dados — HDD 6 TB, não no SSD

- `PGDATA` em **`/data/bestmodel/postgres`** (bind mount; override
  `deploy/docker-compose.omarchy.yml` que também fixa `PGDATA`, pois a imagem
  `timescale/timescaledb-ha:pg16` por padrão usa `/home/postgres/pgdata/data`
  dentro do container — sem o override o dado NÃO cai no HDD).
- `/data` = WDC 6 TB ext4, fstab `UUID=94ab8449-…` `defaults,nofail`, unit
  `data.mount`. Dir `postgres` precisa ser uid 1000 (= carlos = postgres do
  container). Redis/artifacts/caddy ficam em named volumes no SSD.
- Backups locais: **`/data/bestmodel/backups/bestmodel-*.sql.gz`**, timer user
  `bestmodel-backup-hdd.timer` (diário 04:10 -03, `Persistent=true`).
- Backup off-host: timer user `bestmodel-backup.timer` → `deploy/backup.sh` →
  repo privado `carl0sfelipe/bestmodel-backups` (dump SQL + artifacts).
- Restore testado em scratch a partir do .sql.gz do HDD: 551 claims, 78
  modelos, 16 migrations, zero erros.

## Banco (restaurado, não limpo)

Dump de 2026-09-17 restaurado por cima com `--clean --if-exists` +
migrations 0013–0016 aplicadas via `infra/scripts/migrate.py`. Conteúdo:
551 run_claims (import localmaxxing), 78 model_releases, 29 gpu_models,
2 benchmark_runs `validated` (3090/qwen3-8b e wan22-i2v), 1 app_user,
0 passkeys, 0 signing_keys. Janela de perda: 17/09 03:01Z → morte (~1 dia).

## Segredos (recriados — os do beelink perderam-se)

| O quê | Onde |
|---|---|
| `deploy/.env` (senha Postgres nova, forte) | `~/Work/bestmodel/deploy/.env` (chmod 600, gitignored) |
| Chave privada Ed25519 do gate (NOVA) | `~/secrets-bestmodel/gate-key.pem` + `~/.config/benchmark-probe/ed25519.pem` (600) |
| Chave pública confiável | `deploy/secrets/trusted_public.pem` (gitignored, bind-mount ro no api/worker) |
| `TUNNEL_TOKEN` | não usado — túnel é gerenciado via CLI (ver seção Túnel) |

Consequência da chave nova: as 2 runs antigas seguem `validated` no banco
(restore não revalida), mas assinaturas feitas com a chave do beelink não
passam no gate novo (modelo single-signer). CLI local já aponta para o par
novo.

## Front (Vercel) — web-next é o site de prod desde PR #10 (18/09)

- `apps/web-next` (Next.js) serve `www.bestmodel.run`; fala com a API
  **cross-origin** (`NEXT_PUBLIC_API_BASE`), sem rewrite `/v1` (o rewrite do
  `apps/web/vercel.json` antigo não se aplica mais; 404 em `/v1/*` no domínio
  do site é esperado).
- Console estático (`/console/index.html`, versão verbatim do apps/web):
  em 2026-09-18 o fix `94c0205` no main passa `window.BESTMODEL_API` a
  apontar para `https://api.bestmodel.run` (antes base vazia = 404 no app
  Next). **A Vercel não deployou os pushes 94c0205/09a0ec8** (sem deployment
  no GitHub API) — se o console ainda servir config antigo, redeploy manual
  no painel Vercel ou investigar fila.
- `AUTH_EXPECTED_ORIGIN=https://www.bestmodel.run` no `deploy/.env`
  (origem única; o console vive no www; o apex redireciona 308).

## Túnel Cloudflare — ATIVO (gerenciado via CLI, sem TUNNEL_TOKEN)

Feito por CLI no Omarchy (binário `~/.local/bin/cloudflared`, 2026.9.1):

- `cloudflared tunnel login` → `~/.cloudflared/cert.pem` (autorizado pelo
  dono no browser em 2026-09-18).
- Tunnel **`omarchy`** id `a45171df-f0cc-4f74-8072-1ca599446808`, creds em
  `~/.cloudflared/a45171df….json`; ingress em `~/.cloudflared/config.yml`
  (`api.bestmodel.run → http://api:8000`).
- DNS: CNAME `api.bestmodel.run` → tunnel novo (`route dns --overwrite-dns`).
  O túnel morto do beelink chama-se **`bestmodel-api`** (0867cd9e…) e ficou
  intocado na conta; pode ser deletado pelo dono no painel quando quiser.
- Roda como serviço do profile `tunnel` com mount ro de `~/.cloudflared`
  (override `docker-compose.omarchy.yml`, `user: 1000:1000` porque a imagem
  roda nonroot e não leria dir 700). **Não usa `TUNNEL_TOKEN`** — nada a
  colar no `.env`.
- Prova: `https://api.bestmodel.run/v1/submissions/nonce` → 200 (antes
  530/error 1033).

## Quirkes desta máquina

- A sessão atual do `systemd --user` nasceu antes de `carlos` entrar no grupo
  `docker`; os timers de backup executam via
  `ssh -i ~/.ssh/id_zcode_local carlos@localhost` (login novo = grupos novos).
  Após o próximo reboot o hop é redundante, mas inofensivo. `Linger=yes` já
  está ativo.
- Smoke local a partir do host: pegar o IP do container api
  (`docker inspect … IPAddress`) e `curl http://<ip>:8000/v1/…` — a API não
  publica porta no host de propósito (edge via tunnel).

## Não feito (fora do escopo deste reinstalo)

- **OAuth sign-in (S30) ATIVO para GitHub**: primeiro login real em
  2026-09-19 (`github|carl0sfelipe|carl0sfelipe-gh`). App OAuth do dono
  (client `Ov23li…`) com creds em `deploy/.env`. Fixes de produção:
  begin com redirect_uri default (`c640910`) e callback autossuficiente
  com destino dentro do state assinado (`0c1880f` — providers só enviam
  code+state). **HuggingFace segue dormente**: criar o app no HF
  (`docs/en/deploy.md` § OAuth) e preencher `HUGGINGFACE_*` no `.env`.
  Vincular OAuth à conta passkey existente (sem sufixo `-gh`) = backlog.

- Ingestão das medições Modal (L4/A10G chat+code+music) — seguem só no clone
  de um agent box, sem assinatura/upload.
- PR #11 (intent `music`) segue DRAFT; pool-backend ainda checa `chat|code`
  em partes — não misturar com o Postgres social.
- Smoke passkey + bug corrigido: registro para handle JÁ EXISTENTE crashava
  na API (`UUID.replace` AttributeError → 500 sem headers CORS → browser
  mostra "Failed to fetch"). Fix `4b2a253` (str() no user_id), imagem
  rebuildada e prova pública: POST register/options p/ `carl0sfelipe` →
  200 com challenge. A cerimônia WebAuthn final (`navigator.credentials
  .create`) só roda num navegador com autenticador — o dono cria a conta
  dele em https://www.bestmodel.run/console no Chromium dele. User de teste
  `omarchy-smoke` (smoke) foi removido do banco.
- No main do repo, commits desta reinstalação: `94c0205` (console base),
  `09a0ec8` (nudge), `4b2a253` (fix passkey).
- `deploy/docker-compose.omarchy.yml`, este doc e as units user adaptadas
  (path carlos no `bestmodel-backup.service`) estão **não commitados** até
  revisão do dono. No main foram commitados APENAS: fix do console
  (`94c0205`, deployado em Production pela Vercel às 21:39Z) e o nudge
  (`09a0ec8`). A Vercel ficou ~35 min sem reagir a pushes (20:01→21:39Z);
  se repetir, "Redeploy" manual no painel dela.

## Log append-only

- **2026-09-19 — briefing Fable preparado (Grok, sem decisões).** Pacote de
  leitura: `docs/FABLE-BRIEF-2026-09-19.md` → esta escalada
  (`docs/ESCALACAO-FABLE-2026-09-19.md`) → este HANDOFF → direction v2 →
  backlog seletivo. D1–D7 **abertas**. Workspace desta conversa =
  `~/Work/bestmodel`. Untracked à espera do dono: este arquivo,
  `deploy/docker-compose.omarchy.yml`, as duas docs Fable; units systemd
  vivas só em `~/.config/systemd/user/` (cópia git ainda path beelink).
- **2026-09-19 — ponteiros v0 (Grok, ideia para o Fable refinar).** Catálogo
  arcaico `docs/POINTERS.md` (OPEN/SKIP/STALE por job). `AGENTS.md` raiz
  deixa de mandar ingest de 7 arquivos. Não é decisão: o Fable right-size
  no mesmo record (linha, não epic, salvo ele discordar).
- **2026-09-19 — Fable (escalada v3) — decision record em
  `docs/direction-2026-09-19.md`.** Verificado read-only: stack 5/5, 200
  públicos, backups HDD presentes, 17 migrations, 551 claims, 0 votos, 0
  signing_keys; **corrigido: 3 app_users** (`carl0sfelipe` sem passkey,
  `carl0felipe` lixo, `carl0sfelipe-gh` OAuth) → moderação efetivamente
  desligada (H5). kdbx é cofre dos segredos NOVOS, no mesmo host. Decisões:
  D1 hardening leve (kdbx off-host, dump 6h, ping externo; 2ª origem
  rejeitada com precondição); D2 dial `MODERATOR_HANDLES` hoje + story S31
  link (antes do S23b); D3 chave global fica, 2 runs órfãs ficam rotuladas,
  S23b dissolve a classe; D4 rota (a) chat+code já, music após PR #11, raw
  do Modal p/ backup ANTES; D5 web-next único, Pages nunca DR, console
  single-source; D6 nada externo até o dogfood loop fechar, depois S24; D7
  commitar agora (`%h` nas units). Ordem na tabela do record. Ponteiros v0
  adotados (linha + presence grep no S25c).
- **2026-09-19 17:50 — Fable executou ordem 0–1 do record (prod).** H6
  **confirmado e corrigido** (`aaad02f`, deployado: register/options em
  handle com dono sem sessão → 409; órfão → 200; própria sessão → 200).
  Prod DB: token de agente `vast-benchmark-probe` (26/08, rig Vast
  devolvida, sem expiração) **revogado**; usuário typo `carl0felipe`
  apagado; 16 challenges vencidos de `carl0sfelipe` purgados.
  `MODERATOR_HANDLES=carl0sfelipe-gh` no `deploy/.env` (conta que o dono
  controla) até passkey em `carl0sfelipe` + S31. API rebuild `up -d
  --build api`, healthy. D7 commitado (`f601d06`): compose omarchy,
  runbook, POINTERS, direction v3, unit com `%h`. Suíte Python: 339 pass;
  6 falhas só por redis dev 6380 ausente (stack dev não sobe nesta
  máquina; rodado dentro da imagem `bestmodel-prod-api`).
