# Fable brief — 2026-09-19 (pacote mínimo)

> **Você é o Fable. Não escreva código, não rode testes/builds/deploys, não
> depure caso a caso.** Verificar estado → decidir D1–D7 → devolver decision
> record right-sized → assinar o HANDOFF-OMARCHY (append-only). O dono lê
> antes de qualquer execução.
>
> Primeira ação: `docs/POINTERS.md` job `fable-escalation`. Segunda: este
> arquivo. Terceira: a escalada. Não abra o monorepo inteiro.

Workspace: `~/Work/bestmodel` (já é a raiz desta conversa). `main` =
`origin/main` @ `0c1880f`.

## Ordem de leitura (só isto)

Instância do job card em `docs/POINTERS.md`. A tabela abaixo é a cópia
desta escalada; se divergir, **ganha o POINTERS**.

| # | Arquivo | Por quê | Orçamento |
|---|---|---|---|
| 1 | **este arquivo** | mapa atual + o que é stale + o que o ZCode fez sozinho | inteiro |
| 2 | `docs/ESCALACAO-FABLE-2026-09-19.md` | pedido, Verify, Learn, H1–H4, **D1–D7**, formato da resposta | inteiro |
| 3 | `docs/HANDOFF-OMARCHY-2026-09-18.md` | estado da máquina (prod no Omarchy) | inteiro; é curto |
| 4 | `docs/direction-2026-08-29.md` | suas D1–D7 **v2**, ainda vigentes onde não conflitarem | inteiro |
| 5 | `docs/backlog.md` | tracks A–D + dials do dono | só cabeçalho + tracks B/C + decisões 30/08 + S28; **não** reler A1–A11 item a item |

**Não ler** salvo se uma decisão D1–D7 exigir: `findings.md`, `research-2026-08.md`,
`HANDOFF-2026-08-28.md`, specs L01/L02/engine-epics, código. Specs úteis *se*
D3/D4 puxarem: `specs/en/S23-per-user-signing-keys.md` (API já existe; CLI fora
de escopo), `docs/direction-2026-08-28.md` D2 (flywheel: keys antes de campanha).

**Stale — não tratar como verdade operacional:**

- `docs/architecture.md` — grafo de 2026-08; **não tem** web-next, OAuth, Omarchy, S23 dual-path.
- `docs/en/deploy.md` — ainda descreve beelink + rewrite `/v1` no Vercel + Pages como cutover.
- `README.md` lista `apps/web/` como “the site”; prod é `apps/web-next`.
- `docs/backlog.md` **S30** = mural/track-record (31/08). OAuth de 19/09 **reusou o id S30**. Colisão real.
- `deploy/systemd/bestmodel-backup.service` no git ainda aponta `/home/beelink/...`. As units vivas estão em `~/.config/systemd/user/` (path carlos + hop ssh).

Saída obrigatória: o formato no fim da escalada (validação ≤10 linhas, D1–D7
com tamanho epic/story/linha/rejeição + ordem, H5+, append no HANDOFF).

---

## Arquitetura agora (substitui o grafo stale para esta decisão)

Produto: **bestmodel.run** responde “roda / quão rápido / vale a pena?” com
pool medido + preditor calibrado. Tese: *measured beats reported*; claims
importadas **nunca** entram no leaderboard validado (direction v1 D2, vigente).

```text
browser
  ├─ www.bestmodel.run     Vercel = apps/web-next (Next.js, cross-origin → API)
  │    └─ /console         HTML estático copiado de apps/web (fix 94c0205: base = API)
  ├─ carl0sfelipe.github.io/bestmodel   Pages = apps/web (cópia divergente; console quebrado)
  └─ api.bestmodel.run     Cloudflare Tunnel "omarchy" (CLI, sem TUNNEL_TOKEN)
                              └─ desktop Omarchy, stack docker bestmodel-prod
                                   postgres (PGDATA bind /data/bestmodel/postgres no HDD 6TB)
                                   redis + artifacts (volumes no SSD)
                                   api (FastAPI) + intake-worker
```

Loop de medição (inalterado desde Phase 0):

```text
CLI (Rust, Ed25519) → POST /v1/submissions → Postgres + vault + Redis stream
  → worker (evidência, roofline, dedupe, trust) → status validated|quarantined|rejected
  → leaderboard
```

Dois backends de *pool*, não misturar:

| Superfície | Onde | O que é |
|---|---|---|
| Social / verdade de prod | Postgres (migrations 0001–0017) | users, passkeys, oauth, claims, runs, denúncias |
| Snapshot derivado p/ o site | `apps/web-next/public/data/derived/` (+ cópia em `apps/web`) | JSON estático; refresh via pool-backend |
| `apps/pool-backend` | SQLite local do sync | CHECK `category IN ('chat','code')` — **bloqueia `music`** (PR #11 DRAFT) |

Identidade (o débito de D2):

```text
app_user.handle  unique
  ├─ passkey  (WebAuthn)     → carl0sfelipe  = MODERATOR_HANDLES (dono)
  └─ oauth_account           → github|carl0sfelipe → handle carl0sfelipe-gh (sufixo por colisão)
       UNIQUE (provider, provider_account_id)
sessão = bearer 12h, a mesma dos dois fluxos (console não distingue)
link OAuth↔passkey = backlog, não existe
HF OAuth = código no ar, app do dono ainda não criado
```

Assinatura (o débito de D3) — **S23 já está no código, não é um epic virgem:**

- Intake é **dual-path** (`submit_benchmark_run._verify_signature`): sem
  `signature_key_id` → chave global `TRUSTED_ED25519_PUBLIC_KEY_PATH`; com o
  campo → chave do usuário em `signing_key` (migration 0013).
- Tabela `signing_key` em prod = **vazia**. CLI Rust **não** envia
  `signature_key_id` (fora do escopo da story).
- A chave global **é nova** (beelink morreu). As 2 runs `validated` no restore
  ficaram no banco sem revalidação; assinaturas da chave velha **não** passam
  no gate novo.
- Acelerar S23 **não** revive as 2 runs. Multi-signer só ajuda daqui pra frente,
  salvo se alguém também guardar a pública velha como signer histórico — isso
  não está especificado. Decida isso em D3; não assuma que S23 = restore
  criptográfico.

Contrato de run (direction v2, vigente): shape implícito re-declarado em ~10
sítios. Mitigação mecânica **já no ar**: `tests/test_session_contract.py`
(S25). S30 OAuth entrou nesse lockstep (ZCode: zero drift de paridade neste
episódio). S26 (JSONB details / matar enums abertos) **não** começou. S24
(badges de `source_class` no front) **não** tem spec nem código.

Roadmap v2 (29/08), o que já saiu do papel:

| Item v2 | Estado 19/09 |
|---|---|
| S25a/b/c parity + gate vídeo + AGENTS.md | feito (pré-incidente) |
| D7 células Modal L4/A10/A100 | medidas existem num agent box; **não** em prod |
| S23 keys por usuário | schema+API feitos; tabela vazia; CLI não wired; prod ainda single-signer global |
| S24 badges | não começou |
| S26 contrato 0.9.1 | não começou |
| L01 CLI v2 | parcial (A4 topology NVIDIA done; A11 argos-opt é reconstrução vendored) |
| Vast | **suspenso pelo dono** (30/08); não reabrir |

Dials do dono que amarram crescimento: opt-out transparente no contribute
(A3); cloud na superfície pública só como whitelist gamificada; `MODERATOR_HANDLES`
default `carl0sfelipe`; 2º moderador (não uma data) é o gatilho para tabela de
roles (E6/RAT-3).

---

## O que aconteceu sozinho nas últimas ~48h (auditoria, não decisão)

Três mãos, um `main`. Não é uma sessão só.

### A — PRs mergeados 18/09 (outra sessão, *antes/durante* a morte do beelink)

| PR | O quê |
|---|---|
| #3 | `third_party/argos-opt` reconstruído (árvore original perdeu-se com a máquina) |
| #4–#5 | cold-start + self-serve de agentes (topology Linux, `llms.txt`, suggest offline) |
| #6 | claims tier: nunca combo hardware+intent vazio |
| #7 | refresh do pool snapshot (+2383 runs, +174 cells) |
| #8 | bandwidth seed 10→44 (A10) |
| #9 | GitHub Pages auto-deploy de `apps/web` |
| #10 | **cutover**: Vercel passa a servir `apps/web-next`; claims tier + snapshot fresco |

Isto é mudança de front + dados no mesmo dia em que a API caiu. Sem revisão
arquitetural (é o ponto da escalada).

### B — ZCode, incidente 18/09: beelink → Omarchy (não commitado o runbook)

- Dump 17/09 03:01Z restaurado (`--clean`); perda ≈ 1 dia.
- Stack 5/5 healthy; PGDATA forçado no HDD (a imagem timescale-ha ignora o
  bind sem override — `deploy/docker-compose.omarchy.yml`, **untracked**).
- Túnel novo `omarchy`; túnel morto `bestmodel-api` intocado na conta.
- Segredos recriados (Postgres + par Ed25519). Os do beelink não existem mais.
- Backup HDD 04:10 + off-host (repo privado). Restore scratch = zero erros
  (depois de um falso-READY no `pg_isready` do initdb — ver Learn da escalada).
- CI `backup-alarm` tentado neste repo, depois **movido** para
  `carl0sfelipe/bestmodel-backups` (`df736bd`) — alarme 48h existe, fora daqui.

### C — ZCode, 18–19/09: consertos no `main` (commitados)

| Commit | O quê |
|---|---|
| `94c0205` | console **do web-next** aponta para `api.bestmodel.run` |
| `09a0ec8` | nudge Vercel (silêncio ~35 min 20:01→21:39Z; não investigado) |
| `4b2a253` | passkey: register/options 500 em handle já existente |
| `5a02618` | **OAuth GitHub+HF** (id S30, colide com mural) |
| `c640910` | begin: `redirect_uri` default da console de prod |
| `0c1880f` | callback autossuficiente (provider manda só `code`+`state`); teste que imita o GitHub de verdade |

Login real: `github|carl0sfelipe|carl0sfelipe-gh`. HF dormente. Console Pages
**não** recebeu o fix de base (divergência conhecida).

### D — fora do produto, mesma janela

Skill `omarchy-community`; passphrase-helper Segredo↔BIP-39. Irrelevante para
D1–D7.

### E — ainda só na máquina, revisão do dono pendente (é o D7)

Untracked no git: `deploy/docker-compose.omarchy.yml`, este brief, a escalada,
`docs/HANDOFF-OMARCHY-2026-09-18.md`. Units vivas **fora do repo**:
`~/.config/systemd/user/bestmodel-backup{,-hdd}.{service,timer}`.

---

## Hipóteses e decisões — não as feche aqui

H1–H4 e D1–D7 estão na escalada. Este brief só adiciona fatos que a leitura
do ZCode pode ter comprimido demais:

- **S23 ≠ restore das 2 runs.** Schema/API já existem; o buraco é chave global
  rotacionada + tabela vazia + CLI sem `signature_key_id`.
- **S30 é dois artefatos.** Mural (backlog 31/08) vs OAuth (commits 19/09).
- **Claims tier no web-next já entrou** (PR #10). D6 perguntando “claims tier
  no feed?” precisa saber que uma fatia já está em prod.
- **`docs/en/deploy.md` ainda vende Pages como cutover de DNS.** D5 não pode
  tratar Pages como fallback sem notar que o console de lá está errado.
- **SPOF (H1) já se materializou uma vez** (beelink). O Omarchy teve ~15
  reboots em 3 dias (doc local de crash; não reaberto aqui). Backup-alarm
  48h já existe no repo de backups.

Não execute nada. O dono lê o decision record antes do ZCode.

---

## Ideia para você refinar (não é D1–D7)

O dono pediu ponteiros para não pagar o monorepo inteiro. v0 está em
`docs/POINTERS.md`: catálogo arcaico (verb · path · one line), job cards,
lista STALE. O `AGENTS.md` raiz deixou de mandar ingest de 7 arquivos.

Isto é o lado *leitura* do seu D4-v2 (que é lado *edição*). O seu D1-v2
disse que prosa sem mecanismo não muda agente. v0 é prosa.

As 5 perguntas estão no § Fable do POINTERS. Cabe uma linha no decision
record (adotar / rejeitar / gate). Não abra um epic só porque o arquivo
existe.
