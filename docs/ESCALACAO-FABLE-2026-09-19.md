# ESCALADA → FABLE (2026-09-19, v3): bestmodel — beelink morreu, prod renasceu no Omarchy, OAuth no ar; próximos passos estratégicos

> **Start here:** `docs/POINTERS.md` (job `fable-escalation`) →
> `docs/FABLE-BRIEF-2026-09-19.md` → este arquivo. Não abra o monorepo.

> **LEMBRETE PERMANENTE — leia antes de qualquer coisa.**
> Você é caro. **NÃO faça nada que o ZCode (agente local) faz.** Proibido: código,
> testes, builds, deploys, depuração caso a caso. Seu trabalho: **verificar/validar o estado,
> decidir estrategicamente e devolver um plano direcional right-sized.**
> Contexto vivo: `docs/HANDOFF-OMARCHY-2026-09-18.md` (estado da máquina) +
> `docs/direction-2026-08-29.md` (suas decisões v2, ainda vigentes onde não
> conflitarem) + `docs/backlog.md`.

> **Enquadramento BMAD pedido pelo dono.** Trate esta escalada como o loop
> *Clarify → Plan* sobre um sistema que acabou de passar por *Build+Verify* sob
> incidente: o que está abaixo em §3 são fatos verificados (fase Verify), §4 é
> o log de aprendizado (fase Learn), §6 são as decisões que abrem o próximo
> *Plan*. Pedimos um **decision record** right-sized — nem tudo vira epic; alguns
> itens são uma linha no backlog, outros são rejeição explícita.

---

## 1. O pedido do dono (essência)

> "faz um handoff para eu mandar pro Fable **verificar e validar** e **pensar e
> decidir estrategicamente os próximos passos**, usando o método BMAD."

Ou seja: (a) auditar o que o ZCode fez nas últimas 48h (a prod caiu e voltou),
(b) decidir a ordem do que vem agora, com o contexto de que **a produção inteira
mudou de máquina, perdeu segredos, ganhou login OAuth e o front trocou de app
— tudo em dois dias, por sessões diferentes, sem revisão arquitetural.**

## 2. Timeline da janela (só o esqueleto)

- **~17/09 03:01Z** último backup automático do beelink (repo privado off-host).
- **18/09** beelink morre → `api.bestmodel.run` 530/error 1033. PRs #7–#10
  (web-next cutover + pool refresh) mergeados no mesmo dia por outra sessão.
- **18/09 (tarde)** reinstalo completo no desktop **Omarchy** (HDD 6TB): stack,
  restore, túnel novo por CLI, chaves recriadas, backups duplos.
- **19/09** bug passkey corrigido; **OAuth S30** especificado, implementado,
  testado, deployado e **validado com login real** (GitHub). HF dormente.

## 3. Estado verificado (fase Verify — cada linha tem evidência)

**Infra**: stack `bestmodel-prod` 5/5 healthy no Omarchy; PGDATA em bind mount
no HDD (`/data/bestmodel/postgres`; a imagem timescale ignora o path montado
sem override de `PGDATA` — armadilha documentada); túnel `omarchy` (CLI, sem
TUNNEL_TOKEN, `~/.cloudflared`); túnel morto `bestmodel-api` intocado na conta.
**Prova pública**: nonce 200, leaderboard/claims 200 via domínio.

**Dados**: DB **restaurada** do dump 17/09 (não limpa): 551 run_claims, 78
model_releases, 29 gpu_models, 2 runs `validated`, 1 app_user, 0 passkeys
originalmente; janela de perda ≈ 1 dia. Migrations 0013–0017 aplicadas (0017 =
`oauth_account`). Backup HDD diário 04:10 + off-host diário (repo privado);
**restore testado em scratch** com zero erros.

**Segredos**: os do beelink morreram com ele. Recriados: senha Postgres forte,
**par Ed25519 NOVO do gate** (`~/secrets-bestmodel/gate-key.pem` +
`~/.config/benchmark-probe/ed25519.pem`; pública em `deploy/secrets/`, no
container). Consequência não resolvida: as 2 runs antigas seguem `validated`
no banco, mas **assinaturas da chave velha não passam no gate novo**
(single-signer). Tabela `signing_key` continua vazia.

**Auth (S30, novo)**: OAuth GitHub+HF — begin 307, callback autossuficiente
(destino embutido no state assinado), token de sessão 12h no fragmento da URL,
auto-create com sufixo (`-gh`/`-hf`) em colisão de handle. **Login real
confirmado**: `github|carl0sfelipe|carl0sfelipe-gh`. HF aguarda app do dono
(callback documentada). Commits: `5a02618`, `c640910`, `0c1880f`.

**Front**: o prod no Vercel agora é o **web-next (Next.js)**, falando
cross-origin com a API; o rewrite `/v1` do apps/web é legado. Console estático
embarcado no web-next consertado (base apontando pra API, `94c0205`) — o
console na cópia apps/web (GitHub Pages) **segue com base vazia + rota de
report errada** (divergência conhecida entre as duas cópias). Vercel
apresentou ~35min de silêncio em deploys (20:01→21:39Z, sem deployment criado)
— não investigado a fundo.

**Ferramentas do dono** (coadjuvante): skill `omarchy-community` criada
(pesquisa determinística em omacom/omarchy + manual + ArchWiki);
`passphrase-helper` ganhou Segredo↔BIP-39 (não afeta bestmodel).

## 4. Log honesto (fase Learn — erros que cometi, com causa-raiz)

1. **Cego de teste no OAuth**: o callback exigia `redirect_uri` que provedor
   nenhum envia; TODOS os testes passavam porque eu construía a chamada à mão
   com o parâmetro que o GitHub não manda. Fix + teste-regressão que reproduz
   o redirect real (`0c1880f`). *Lição: mock que imita o autor, não o mundo.*
2. Diagnóstico errado na primeira tentativa (tratei sintoma no `begin`; o bug
   era no `callback`) — custou um roundtrip do dono.
3. Falso-READY no teste de restore: `pg_isready` respondeu ao servidor
   **temporário do initdb** — teste "passou" sem restaurar nada; refiz com
   espera pelo servidor real.
4. `psql -c` com statements múltiplos rola tudo back se um falha — cleanup do
   user de teste precisou de 2 tentativas.
5. PGDATA da timescale-ha (§3) — dado teria ficado no SSD sem o lsblk pós-boot.

*(Para a sua D1-v2: o lockstep ABC/Postgres/Fake agora tem gate mecânico
(`tests/test_session_contract.py`) e o S30 entrou nele — o mecanismo da sua
direction-2026-08-29 funcionou neste episódio: zero drift de paridade.)*

## 5. Hipóteses (confirme, refute ou refine)

- **H1 — Single point of failure piorou**: a prod inteira (API + worker + DB +
  túnel) vive num único desktop que já teve ~15 reboots em 3 dias (set/2026,
  doc de crash local). O beelink morreu; o Omarchy não tem par.
- **H2 — Identidade fragmentada é débito agora**: o mesmo humano existe como
  `carl0sfelipe` (passkey, dono, moderador) e `carl0sfelipe-gh` (OAuth).
  MODERATOR_HANDLES aponta pro handle passkey — o login GitHub do dono NÃO
  modera.
- **H3 — O flywheel tem rotação zero fora do dono**: 551 claims importados +
  login fácil agora, mas nenhum usuário real além do dono; as medições Modal
  (L4/A10G chat+code+music) continuam fora de prod.
- **H4 — Front duplicado custa**: duas cópias do console divergem (bugs
  conhecidos na do Pages); web-next e apps/web coexistem sem decisão de
  consolidação.

## 6. Decisões que preciso de você (uma decisão + porquê curto por item)

- **D1 — Resiliência da prod**: aceitar Omarchy único + backups (estado atual)
  vs leve hardening (e.g.: monitoring externo além do backup-alarm, teste de
  restore agendado, DR runbook) vs segunda origem barata (túnel+cold standby).
  O que é right-sized para o estágio?
- **D2 — Modelo de identidade**: link OAuth↔passkey (fim do sufixo, uma conta
  por humano) — fazer quando, e o mínimo viável (fluxo autenticado de link no
  console?). Inclui: OAuth conta como requisito de reputação L0 ou herda?
- **D3 — Chave do gate pós-perda**: manter single-signer com a chave nova vs
  acelerar **S23 (signing keys por usuário)** tornando o gate multi-signer e
  dissolvendo o problema. A janela "runs antigas órfãs" incomoda?
- **D4 — Células Modal (L4/A10G)**: rota de publicação — (a) contribute/sign
  com chave owner como `measured`, (b) pipeline derived do pool com
  source_class explícito, ou (c) segurar até S23. E a dependência **PR #11 /
  `music`** (pool-backend ainda CHECK `chat|code`): ordenar o que primeiro?
- **D5 — Front único**: consolidar em web-next (deletar/redirect da cópia
  Pages, portar o que falta) vs manter as duas conscientemente. A Vercel
  flaky entra na decisão (Pages como fallback)?
- **D6 — Ativação**: com login sem fricção no ar, qual o próximo passo de
  crescimento right-sized — S24 badges no front? claims tier no feed? um
  "measurement challenge" usando o modal credit? Ou nada até estabilizar?
- **D7 — Dívida de sessão**: `deploy/docker-compose.omarchy.yml` +
  HANDOFF-OMARCHY + units user adaptadas seguem **não commitados** à espera de
  revisão do dono; console Pages quebrado (§3). Confirmar prioridade destes
  itens pequenos vs D1–D6.

## Formato da resposta esperado (BMAD: saída do Plan)

1. **Validação do estado** (§3): o que endossa, o que rejeita, o que faltou
   verificado — máx. 10 linhas.
2. **Decision record D1–D7** com o tamanho certo de cada item (epic / story /
   linha de backlog / rejeição explícita) e a ordem de execução — é a saída
   central.
3. **Riscos que eu não listei** (H5+): o que a sua leitura vê que a minha não.
4. Assine o HANDOFF-OMARCHY (linha append-only) com as decisões.
5. **Ponteiros (pedido extra do dono, não é D1–D7):** uma linha sobre
   `docs/POINTERS.md` v0 — adotar / rejeitar / tornar mecânico. Perguntas
   no § Fable daquele arquivo. Right-size: quase certamente uma linha, não
   um epic.

*Assinado: ZCode, 19/09/2026. O dono lê sua resposta antes de qualquer execução.*
