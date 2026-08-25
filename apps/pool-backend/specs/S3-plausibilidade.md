# S3 — Plausibilidade física

Depende de: S2. Produz: `src/plausibility.py`, alvo `flags`, endpoint
`GET /v1/plausibility/summary`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte
> além dos listados em "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub/`declare const`/mock como workaround de import — importe de
> verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(backend-S3): ...`; mate qualquer servidor que subir
> (`pkill -f "uvicorn.*8790"`).

## Objetivo

Recomputar o teto roofline de cada run e gravar o verdict. É a curadoria que
o concorrente não faz sobre os próprios dados — e o insumo para os agregados
limpos da S4.

## Dados verificados

- Fórmula do teto, verdicts, isenções e frações: CONTRATO §6, fechados.
  A regra física (decode ≈ bandwidth ÷ GB por token) é publicada pelo próprio
  localmaxxing; as frações 0.92/1.05 vêm da regra roofline da Fase 0 do
  monorepo (finding F2/A5) e da tolerância de medição.
- Runs com especulação/MTP legítimos existem no pool (o topo do leaderboard
  deles usa MTP) — por isso o verdict `exempt`, nunca flag de fraude.

## Saídas exatas

- `src/plausibility.py`: executável (`uv run python -m src.plausibility`);
  recalcula TODAS as flags (DELETE + INSERT em transação única) — flags são
  derivadas, recompute total é barato e evita estado velho.
- Endpoint `/v1/plausibility/summary` em main.py conforme CONTRATO §7.
- Alvo `flags` no check.py.

## Spec

1. Para cada run de lm_run: aplicar §6 na ordem — isenções primeiro (reason
   literal: "spec_decoding", "mtp_enabled", "batch_gt_1", "concurrency_gt_1",
   "missing_inputs"), depois ratio -> verdict. `reason` de
   ok/suspicious/impossible = "ratio_vs_ceiling".
2. `ceiling_tok_s` e `ratio` gravados com 4 casas; `computed_at` ISO único da
   rodada.
3. Summary: contagens por verdict + top 10 `impossible|suspicious` por ratio
   desc com runId/modelSlug/rigKey/ratio.
4. `check.py flags` valida: `COUNT(plausibility_flag) == COUNT(lm_run)`;
   todo verdict ∈ {ok,suspicious,impossible,exempt}; nenhum run isento tem
   ratio calculado contra bandwidth NULL (missing_inputs cobre); summary do
   endpoint bate com SQL direto (tolerância zero).

## O que NÃO fazer

- Não incluir leitura de KV no teto (decisão do §6: teto superestimado de
  propósito); não inventar tetos de prefill/TTFT (fora do v1).
- Não publicar username de quem submeteu run impossível (dado deles, pessoas
  reais; expomos run ids e agregados, não pessoas).
- Não deletar/alterar lm_run.

## Verificação

```bash
uv run python -m src.plausibility
uv run python scripts/check.py flags
uv run uvicorn src.main:app --port 8790 &
curl -s localhost:8790/v1/plausibility/summary | python3 -m json.tool | head -20
pkill -f "uvicorn.*8790"
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f src/plausibility.py && uv run python scripts/check.py flags
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: fração de `impossible` entre runs NÃO-isentos passar de
15% (ou a fórmula está errada, ou o pool é pior do que o esperado — humano
olha os top 10 antes de seguir; não afrouxe frações por conta própria).
