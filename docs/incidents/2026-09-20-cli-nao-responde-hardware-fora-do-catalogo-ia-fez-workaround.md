---
id: 2026-09-20-cli-nao-responde-hardware-fora-do-catalogo-ia-fez-workaround
titulo: CLI e site do bestmodel nao respondem para hardware fora do catalogo (Galaxy S25 Ultra); uma IA respondeu por workaround
data: 2026-09-20
recorrivel: sim
regra: nao — candidata: "pergunta fora do catalogo responde com fonte externa ROTULADA e abre item de catalogo" (mesma classe de 16/23: falha recorrente vira protecao; o mecanismo esta na spec S32, nao neste diario)
status: aberto
repo: bestmodel (produto) + sessao Cursor cloud (agente Fable) — copia deste arquivo vive em bestmodel/docs/incidents/; o original e o diario privado
interage_com: reforca 16 e 23 (workaround repetido vira mecanismo); reforca 32 (cada workaround abaixo declara o mecanismo deterministico que o substitui); nao supera a direction v1 D2 (numero de fornecedor e claim, nunca celula)
workarounds:
  - id: W1
    manual: buscar specs do SoC (RAM, banda, NPU) em GSMArena + product brief da Qualcomm
    deterministico: registry apps/web/data/seed/mobile-socs.json + linhas gpu_model com form_factor=phone (S32a, S32e)
  - id: W2
    manual: transcrever tabelas "Performance Summary" da Qualcomm AI Hub (HF) para tok/s por modelo
    deterministico: infra/scripts/import_qai_hub.py -> run_claim com provenance, idempotente (S32d)
  - id: W3
    manual: calcular de cabeca "cabe em 12 GB a Q4?" e o efeito de ~85 GB/s vs 936 GB/s
    deterministico: roofline prior com form_factor=phone e caveat de memoria do Android (S32e); transfer por banda no canirunit (S32g)
  - id: W4
    manual: identificar o aparelho pelo user agent e escolher "o rig mais parecido"
    deterministico: lib/device.ts via UA Client Hints (model SM-S938B) + grupo "Phones & tablets" no seletor (S32b)
  - id: W5
    manual: listar de memoria os SOTAs mobile (Gemma 4 E2B/E4B, Qwen3.5 2B/4B, LFM2.5, Ministral 3, Phi-4-mini, Nemotron 3 Nano)
    deterministico: expand_catalog_from_hf.py com a lista de ids HF, zero numero digitado (S32c)
  - id: W6
    manual: QA a mao do llms.txt de prod apontando para m/index.html (404)
    deterministico: apps/web-next/scripts/check-mobile.mjs — todo caminho anunciado responde 200 (S32b)
  - id: W7
    manual: "e como eu mediria no proprio telefone?" respondido com Termux + llama-cli de cabeca
    deterministico: benchmark-probe com target_os=android + secao no agent-quickstart (S32f)
  - id: W8
    manual: interpretar o "closest rig ids" do canirunit (arc-b580-12gb para um celular) como ruido
    deterministico: gpu_transfer_specs.json chaveado por rig key + transfer de decode_tok_s por banda, nao por TFLOPS (S32g)
---

# CLI e site nao respondem para hardware fora do catalogo; a IA respondeu por workaround

Contexto: o dono comprou um Galaxy S25 Ultra e perguntou ao produto a
pergunta que o produto existe para responder — "o que roda nele, quao
rapido, vale a pena?". A resposta veio de uma sessao de agente (Cursor
cloud, ~1h30 de parede, dezenas de chamadas de ferramenta, 9 buscas web,
uma sessao de browser emulado), nao do bestmodel. O agente produziu a
resposta correta e rotulada, mas cada passo foi um workaround humano/IA
sobre uma lacuna deterministica do produto. Este diario registra os
passos para que, quando a lista de workarounds crescer, o padrao vire
mecanismo (ciclo incidente -> protecao).

## Sintoma

Reproducao deterministica no clone publico, `main` `16cf014`, pool
snapshot `2026-09-18T17:08:19.808Z` (1753 celulas):

```text
$ cargo build -p canirunit
$ ./target/debug/canirunit rigs --runs apps/web/data/derived/pool.json --filter galaxy
no rig id matches 'galaxy' in 'apps/web/data/derived/pool.json' — drop --filter to list them all
exit=3

$ ./target/debug/canirunit rigs --runs apps/web/data/derived/pool.json --filter snap
cpu-qualcomm-snapdragon-888-arm64          # unico celular Qualcomm no pool: 1 run

$ ./target/debug/canirunit suggest --gpu snapdragon-8-elite-12gb --task decode_tok_s \
    --runs apps/web/data/derived/pool.json --gpus cli/canirunit/gpu_transfer_specs.json
{ "match_class": "unknown", "suggestions": [],
  "explanation": "no measured runs for gpu 'snapdragon-8-elite-12gb' ... be the first to publish a signed run" }
no data for 'snapdragon-8-elite-12gb' — closest rig ids in this corpus:
  arc-b580-12gb, cpu-qualcomm-snapdragon-888-arm64, rtx-3060-12gb, rtx-3060-12gb-x2, rtx-3080-12gb
exit=3
```

Tres falhas distintas nessa saida:

1. **Catalogo**: nao existe rig, `gpu_model` nem spec de transfer para
   Snapdragon 8 Elite (nem Apple A-series, Tensor, Dimensity). O unico
   celular Qualcomm e um Snapdragon 888 classificado como `CPU_ONLY`,
   com 1 run (Gemma 4 E2B, 6.2 tok/s) e banda `null`.
2. **Transfer nunca dispara**: `--gpus` deveria estimar por roofline a
   partir de um rig ancora. Mas `gpu_transfer_specs.json` tem 5 GPUs
   desktop com ids `gpu-rtx-3090`, `gpu-rtx-4090`... enquanto o pool usa
   `rtx-3090-24gb`; `transfer_suggestions` exige
   `specs.contains_key(run.gpu_model_id)` — com o snapshot do repo o
   caminho de transfer e codigo morto para QUALQUER gpu, nao so celulares
   (verificado: `--gpu gpu-rtx-3080` tambem cai em `unknown`). E o fator
   e razao de fp16 TFLOPS (compute-bound, escrito para difusao); decode
   de LLM e limitado por banda — o estimador certo para a pergunta do
   dono nem existe no binario.
3. **"Did you mean" mente por similaridade de string**: `arc-b580-12gb`
   e `rtx-3060-12gb` aparecem como "closest" a um celular porque
   compartilham `12gb`. Um leitor humano descarta; um agente barato pode
   seguir a dica e responder com numero de Arc B580 para um Galaxy.

No site (prod `www.bestmodel.run`, sessao 412x915 com UA `SM-S938B`): o
seletor da home tem exatamente 24 opcoes e zero celulares
(`RIG_LIMIT = 24` em `apps/web-next/app/page.tsx`); a pagina abre com
`CMP 170HX 64GB · 255.9 tok/s` pre-selecionado; `/llms.txt` manda
leitor mobile para `m/index.html` -> 404; `/submit` nao tem picker de
hardware e o probe Rust nao detecta nada sob `target_os = "android"`.
Detalhe completo: `docs/QA-MOBILE-DOGFOOD-2026-09-20.md` (M1-M14).

## O que a IA fez no lugar do produto (o workaround, passo a passo)

| # | Pergunta do dono | O que o produto devia responder | O que o agente fez |
|---|---|---|---|
| W1 | "me fale dele" | ficha do rig do catalogo | 3 buscas (GSMArena, product brief Qualcomm, Android Authority) e derivou 84.8 GB/s a mao |
| W2 | "o que roda nele" | celulas medidas/reported ou claims rotuladas | leu as tabelas HF da Qualcomm AI Hub (Gemma 4 E2B 26.7-30.4 tok/s, E4B 16.0-17.2 no 8 Elite) e a pagina LiteRT-LM (S26 Ultra) e rotulou tudo como vendor-reported |
| W3 | "cabe? quao rapido?" | fit por formula + prior roofline | conta de cabeca: 12 GB compartilhados, Q4 de 1-4B "instantaneo", 8-9B "curiosidade" |
| W4 | (abriu o site no celular) | seletor oferece o aparelho ou o grupo "phones" | nada; o agente leu o codigo para explicar por que nao aparece |
| W5 | "os SOTAs que rodam mobile" | filtro form_factor=phone no catalogo | lista de memoria + busca Luxand/XDA para tamanhos em disco |
| W6 | "como eu usaria o bestmodel nele" | jornada mobile funcional | QA manual: curl com UA, browser emulado, screenshots |
| W7 | "como eu mediria" | probe roda no aparelho | descreveu Termux + llama-cli lendo `detect_runtime_installations.rs` |
| W8 | (canirunit) | transfer roofline por banda | ignorou o "closest rig ids" e explicou por que e ruido |

Custo aproximado: 9 buscas web, 2 fetches de paginas HF, 1 sessao de
browser (2 rodadas), ~60 chamadas de ferramenta, ~1h30 de parede. Nada
disso e reprodutivel por outro agente sem repetir o trabalho — a menos
que vire mecanismo.

## Causa

1. **O catalogo de hardware nasceu desktop.** `gpu_model` exige
   `tdp_watt NOT NULL > 0`; o vocabulario de classe do pool upstream e
   `DISCRETE_GPU | UNIFIED | CPU_ONLY`; nao existe `form_factor`. Celular
   nao cabe no schema, entao nunca entrou.
2. **O pool importado e desktop.** Das 1753 celulas, 1 e de celular. Sem
   celula, o produto so tem a escada de honestidade ate "claim" — e nao
   tem canal para claims de fornecedor (Qualcomm AI Hub publica tabelas
   por chipset, ninguem as importa).
3. **O caminho de transfer foi escrito para outra pergunta** (difusao,
   compute-bound) e nunca foi chaveado para o snapshot do repo. Ninguem
   percebeu porque o gate exercita o leaderboard export, nao o
   `pool.json` que o `llms.txt` manda o agente usar.
4. **A jornada mobile foi construida no front legado** (`apps/web/site/m/`)
   e nao migrou para o web-next no cutover (PR #10); o `llms.txt` foi
   copiado sem revisar os caminhos.
5. **Nao ha "pergunta fora do catalogo" como evento.** Quando o CLI diz
   `unknown` e sai com 3, nada registra que alguem perguntou por
   `snapdragon-8-elite-12gb`. A demanda que justificaria o item de
   catalogo evapora.

## Correcao aplicada

Nenhuma no produto nesta sessao (decisao: specs, nao codigo — o
executor sera despachado pelo llms.surf).

- PR https://github.com/carl0sfelipe/bestmodel/pull/12:
  `specs/en/S32-mobile-soc-support.md` (historias a-g, um oraculo cada)
  e `docs/QA-MOBILE-DOGFOOD-2026-09-20.md` (M1-M14, com evidencias da
  sessao ao vivo). A tabela `workarounds` no frontmatter deste arquivo
  aponta W1-W8 para a historia que os mata.
- Este diario. Copia em `bestmodel/docs/incidents/`; original no diario
  privado do llms.surf (`incidents/`), mesmo nome de arquivo.

## Pode acontecer de novo?

Sim, e vai: a mesma cascata dispara para qualquer hardware fora do
catalogo — Pixel (Tensor), iPhone (A18/A19), Jetson, Raspberry Pi,
Steam Deck, Mac mini M4 em configuracao nova. O padrao e "pergunta fora
do catalogo -> agente responde por busca externa". Enquanto S32 nao
landa, o que este diario compra e a **contagem**: cada nova ocorrencia
adiciona linhas `W<n>` com o par manual/deterministico. Quando o mesmo
`deterministico` aparecer em >= 3 incidentes, ele sobe de "candidata" a
regra numerada e o mecanismo (S32x ou equivalente) entra na fila com
prioridade — nao antes, para nao construir catalogo por especulacao.

Sinal barato para capturar a demanda desde ja (linha, nao historia):
`canirunit suggest` com `match_class: unknown` deveria emitir uma linha
`unknown_hardware_query` num ledger local (`~/.bestmodel/queries.jsonl`)
com o id pedido e a data — o proprio produto passa a contar as perguntas
que nao soube responder. E a versao offline do "capture one and it stops
being empty" que a home ja promete.
