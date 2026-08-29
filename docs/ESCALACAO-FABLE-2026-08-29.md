# ESCALADA → FABLE (2026-08-29, v2): bestmodel — causa crônica dos erros + arquitetura + insights externos

> **LEMBRETE PERMANENTE — leia antes de qualquer coisa.**
> Você é caro. **NÃO faça nada que um estagiário (ou o ZCode, agente local no coding plan) faz.**
> Proibido para você: escrever código, rodar testes/builds, portar arquivos, depurar casos individuais.
> Seu trabalho aqui: **diagnóstico meta (causa crônica), decisões arquiteturais e um plano direcional.**
> Arquivo pontual só se for spec/matriz de decisão — nunca implementação.
> Contexto vivo: `docs/HANDOFF-2026-08-28.md` (bastão §7, L03 completo) + `docs/findings.md`.

---

## 1. O pedido do dono (essência, de conversa com ele)

> "vejo que tem muitas lacunas [no bestmodel] e o nível de complexidade de código está acima da capacidade cognitiva [do ZCode / talvez de toda LLM atual]. Eu dependo do ZCode — gastei meus últimos centavos num plano anual de tokens. Essa quantidade de tentativas falhas é inaceitável. Passa pro Fable os últimos erros — não pra identificar o bug individual, mas **a causa crônica de tantos erros**: como mudar o projeto **arquitetonicamente**; **specs permanentes em cada pasta** explicando os gotchas pra o próximo agente; talvez **campos de run: poucos obrigatórios, muitos opt-in**."

Ou seja: meta-análise, não bugfix. Ele mandou as tentativas em fila de propósito (esperando auto-resolução) e o padrão de erro é o dado central desta escalada.

## 2. Log honesto dos erros — a evidência bruta

Sessão 28–29/08, execução da Story 1.4 (primeira run de vídeo ponta a ponta) + fechamento L03. Cada linha: sintoma → causa-raiz. **Nenhuma dessas linhas foi pega por teste unitário;** as primeiras 3 nem pelo gate.

**Cluster A — drift FakeDatabase ↔ PostgresSession (o mesmo defeito 3×):**
1. POST 500 em runtime: PostgresSession faltando 7 métodos do ABC (merge U4 portou a interface, esqueceu os corpos — testes passavam via FakeDatabase)
2. Leaderboard vazia: `fetch_leaderboard_entries` (Postgres) não selecionava `run.source_class`/`recipe_id`/escalares de vídeo — o filtro "sem source_class não renderiza" cortava tudo (testes: fake monta dicts direto)
3. `insert_scenario` gravava só 6 colunas LLM → CheckViolation em cenário vídeo; `insert_benchmark_run` idem (derrubava recipe_id/source_class/escalares)

**Cluster B — worker sem caminho de vídeo (4 defeitos na mesma função):**
4. `int(None)` na dimensão (vídeo não tem tokens)
5. parser de evidência exigia chaves LLM (ttft_ms etc.) em run de vídeo
6. consistência de duração sem branch frames/frames_per_s
7. hidratação `fetch_run_payload` com SQL da era LLM (evento Redis minimal só carrega run_id; o payload vem do Postgres)

**Cluster C — decisões de design longe do ponto de mudança:**
8. Adicionei métricas de vídeo ao `METRIC_UNITS` → quebrou teste que codifica **AD-1** ("métricas de vídeo são escalares do run, NÃO linhas benchmark_metric"). A decisão vivia numa spec que eu mesmo portei — e não estava visível no ponto onde troquei. Criei até uma migration 0013 desnecessária e a reverti.

**Cluster D — specs/skeletons nunca validados contra a realidade:**
9. Template de workflow (skeleton "from docs") usava kwargs que **não existem** no node real (`high_noise_model` no `WanFirstLastFrameToVideo`); reescrevi no formato oficial two-pass validando contra o código do ComfyUI instalado (fonte primária)
10. Nomes fp16 no template vs arquivos fp8 baixados; edge `WanFirstLastFrameToVideo[0]` vs `[2]`

**Cluster E — drift de ambiente/orquestração (rig alugada):**
11. Binário do probe compilado no Arch (glibc 2.39) não roda na rig Ubuntu 22.04 (2.35) → rebuild em container ubuntu:22.04
12. `--scenario <path>` vs CLI unificado que só aceita inline/stdin
13. Cascata de disco cheio: aria2 pré-aloca arquivo inteiro + ComfyUI segurando 14GB de arquivo deletado + 2 curls meus competindo pelo mesmo staging
14. Meu "sha256 oficial" era o hash do redirect xet (Merkle do CAS), não o sha256 do LFS pointer → falsa falha + re-download desnecessário
15. Script da rig gerou chave de assinatura própria (não copiou a confiada) → re-assinei local o digest (esquema simples: Ed25519 sobre o texto do digest)

**Cluster F — ordem de deploy:**
16. Upload da célula exigia schema L03 em prod (enum runtime_engine sem 'comfyui', pydantic sem vídeo) — o deploy "gated pós-célula" foi invertido pela realidade: a célula NÃO entra sem o deploy. (Backup feito antes; migrations aditivas aplicadas limpas.)

Estado final: célula `2ced2df3` **validated** (4270s/clipe, 24114MiB = 98% VRAM → infeasible pela margem 95%, escondida da leaderboard por design §11.10); gate PASS; commit `0d621d4` pushado. Ou seja: chegou, mas pelo caminho mais caro possível em tentativas.

## 3. Minha hipótese prévia (confirme, refute ou refine — é aqui que vale seu juízo)

- **H1 — Shotgun change:** um campo novo de run exige tocar ~10 pontos sem nenhum teste que force a cadeia: domain-schema, escalares na migration, FakeDatabase, ABC, corpos PostgresSession (SELECT e INSERT), SQL de hidratação do worker, chaves de evidência, SELECT do leaderboard, builder do CLI, seed de catálogo, gate. Cada ponto é uma chance de esquecimento silencioso (os testes passam porque o fake não conhece o Postgres).
- **H2 — Gate cego pra vídeo:** o gate e2e só exerce POST LLM mock. Nenhum caminho de vídeo atravessa Postgres até produção. Um POST vídeo-mock no gate teria pego os clusters A+B antes.
- **H3 — Conhecimento tribal não-persistido:** decisões (AD-1, margem 95%, "engine code wins") vivem em specs históricas, não no ponto de código onde um agente vai editar. AGENTS.md raiz existe, mas não há spec por pasta com os gotchas.
- **H4 — Rigidez schema-enum:** `metric_kind`, `runtime_engine`, colunas NOT NULL por kind — cada kind novo vira migration+enum+N sítios. A intuição do dono ("poucas obrigatórias, muitas opt-in") aponta pro mesmo lugar: talvez 6-8 campos obrigatórios (identidade, hardware_fingerprint, source_class, runtime, 1 métrica principal) e o resto opt-in/JSONB versionado.

## 4. Decisões que preciso de você (uma decisão + porquê curto por item)

- **D1 — Causa crônica:** qual é a origem dominante dos clusters A–F? (H1–H4 batem? falta algo estrutural — ex.: port de merge manual entre dois repositórios sem ancestry comum foi intrinsecamente propenso a erro?)
- **D2 — Arquitetura de schema:** endossa "poucos obrigatórios + muitos opt-in"? Como, concretamente: colunas nullable vs blob JSONB `extra` versionado por `schema_version`? O que nunca pode virar opt-in (honestidade: source_class, assinatura)?
- **D3 — Paridade fake↔real:** como garantir que FakeDatabase e PostgresSession nunca divergem de novo — contract test gerado da lista de métodos do ABC rodando os DOIS backends com as mesmas asserções? snapshot test de SQL? Ou matar o fake e o gate virar o único teste de integração?
- **D4 — Specs permanentes por pasta:** formato e mecanismo (AGENTS.md por pacote? header-comment canônico em cada módulo com "SE TOCAR AQUI, TAMBÉM TOCAR EM…"?). Quem escreve/mantém e quando (gate checa presença?).
- **D5 — Gate vídeo:** adicionar POST vídeo-mock (comfy sem execute) + validação worker no `make gate`? (estimativa ZCode: ~1h de execução — só confirme o formato)
- **D6 — Insights GPT 5.6 (Anexo A):** consolidar no roadmap. MUITO já existe no bestmodel (source_class = confidence tiers; "measured beats reported" = honesty ladder; anti-hype = tom atual). O genuinamente novo: **R$/tok/s como métrica de primeira classe**, **fingerprint de hardware rico (RAM channels, PCIe, motherboard)**, **avisos de incomparabilidade**, **AI Deal Hunter / perguntas p/ anúncio usado**, **fontes de ingestão**. O que entra, em que ordem, e o que rejeitar (ex.: OCR de OLX agora = scope creep?).
- **D7 — modal.com (US$9 de crédito do dono):** para inferência/planejamento — ex.: células de âncora em famílias de GPU que não temos (L4/A10/A100 via modal, ~$0.3–1/h) alimentando o transfer roofline, sem tocar Vast. Vale? Prioridade vs S23 (chaves por usuário)?

## 5. Contexto coadjuvante (não gaste tokens aqui além do necessário)

speech.baby (mesma rig, ~$3 de saldo Vast): pivô sprites+fade validado; painel HITL v2 pronto; ~5 poses reprovadas (L/QUA/O/U — causa: poses canônicas ausentes no vídeo-fonte ou crop). A decisão de método (regen vs filmagem própria) continua sua da escalada v1 se quiser opinar; **assets que exigirem runs de inferência → planejar no modal.com (crédito do dono), não na Vast**. Rig atual continua até o teardown pós-vídeos.

## Anexo A — Insights GPT 5.6 (destilado pelo ZCode; pedido do dono: consolidar + refinar)

Tese central: **"Don't buy hardware. Buy inference."** — comparar máquinas por valor econômico de inferência:
1. **R$/tok/s** como métrica-mãe: preço da máquina ÷ decode tok/s num workload declarado (máquina "pior" ganha de "melhor" no custo por tok/s; exemplo X99 quad-channel R$5.9k vs i9 dual-channel R$12k, ambos 3090)
2. **Benchmark fingerprint obrigatório** — "16 tok/s é inútil sem contexto": GPU/VRAM/count, CPU, **RAM canais (dual/quad/octa) + banda**, PCIe version/lanes, storage; modelo (params totais/ativos, quant, formato, tamanho arquivo, contexto); runtime (backend+versão, offload camadas/RAM/SSD, KV cache, batch, **speculative/MTP/n-grams**); resultados (prefill/decode/TTFT, VRAM, RAM, watt, temp, estabilidade); fonte+confiança
3. **RAM importa em offload** — quad-channel pode dobrar o throughput com weights na RAM; avisos automáticos: "este resultado depende de quad-channel", "pode não valer p/ contexto maior"
4. **Níveis de confiança** measured/reported/extrapolated/formula/no-data *(ZCode: já existe como source_class + pesos 0.9/0.6/0.4/0.4 — GPT reinventou; a novidade é a linguagem de badge/tooltip pro usuário final = S24)*
5. **Avisos de incomparabilidade** — nunca comparar direto quant/ctx/backend/flags especulativas sem warning *(novo; hoje o leaderboard filtra por dimensão mas não avisa)*
6. **AI Deal Hunter** — orçamento+modelo+quant+ctx → máquinas ordenadas por R$/tok/s com confiança/risco + **gerador de perguntas p/ validar anúncio usado** (2×32 ou 4×16? thermal throttling? PCIe lanes livres?)
7. **Ingestão** de fontes externas (Reddit, HF, GitHub issues, YouTube) priorizada measured>reported>… *(ZCode: harvesters 4.1–4.4 já portados; deal hunter e peruntas são novos)*
8. Schema JSON completo sugerido pelo GPT (benchmark fingerprint com pricing) está no paste original se precisar — núcleo acima cobre o essencial
9. Tom do produto: técnico, honesto, anti-hype — "Benchmarks without context are noise" *(já é o tom)*

## Formato da resposta esperada

1. **Diagnóstico da causa crônica** (D1) — o centro da escalada
2. **Plano arquitetural** (D2–D5): mudanças concretas na ordem que reduz mais erros por esforço, com o que o ZCode executa em specs/roteiro (você não implementa)
3. **Consolidação do Anexo A** (D6): backlog enxuto, marcando o que já existe
4. **Plano modal.com** (D7) se endossar
5. Assine o §7 do HANDOFF (linha append-only) com as decisões

*Assinado: ZCode, 29/08. O dono lê sua resposta antes de qualquer execução.*
