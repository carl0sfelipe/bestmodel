# S2 — Banco + sincronização do pool

Depende de: S1. Produz: `src/db.py`, `src/sync_pool.py`, alvo `sync`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md` (e o contrato web §3/§4/§6
> referenciado). Não invente número, prazo ou fonte além dos listados em
> "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub ou `declare const` como workaround de import — importe de verdade.
> Oráculo verde => atualizar ESTADO.md + UM commit `feat(backend-S2): ...`.

## Objetivo

Materializar o pool público do localmaxxing em SQLite local, idempotente
(rodar duas vezes não duplica), com normalização de identidade idêntica à do
pack web (rigKey/slug/bits — mesma regra, mesmos resultados).

## Dados verificados

- Endpoints, envelopes (`speedTests`!), paginação, etiqueta: contrato web §3
  (parte deste contrato por referência). Total 2026-08-12: 5.026 runs,
  ~687 models.
- DDL: CONTRATO §4 deste pack, literal.
- Regras de identidade e quant->bits: contrato web §4/§6.
- Campos engineFlags usados (verificados no wire): `specDecoding`,
  `mtpEnabled`, `concurrency`.

## Saídas exatas

- `src/db.py`: `connect()` (cria diretório, PRAGMA foreign_keys=ON) e
  `migrate(conn)` aplicando o DDL do §4 exatamente.
- `src/sync_pool.py`: executável (`uv run python -m src.sync_pool`);
  baixa speed-tests e models completos (httpx, throttle §5, retry 2x com
  backoff 2 s), upsert por chave primária; grava em `sync_meta`:
  `last_sync_at` (ISO), `remote_total` e `synced_runs`.
- Alvo `sync` no check.py.

## Spec

1. Ordem de upsert: models -> rigs -> runs (FKs). Rig nasce do bloco
   `hardware` de cada run (regra rigKey); `run_count` recalculado ao final
   com um UPDATE agregado.
2. Runs: só `status == "APPROVED"` e `tokSOut > 0`. `bits` via tabela
   quant->bits (função local `quant_bits()` espelhando o web §6, com os
   mesmos casos: Q4_K_M->4, Q8_0->8, NVFP4->4, fp16->16, IQ3_XS->3,
   Unsloth-Dynamic-Q4_K_M->4, desconhecido->NULL).
3. `raw_json` guarda o registro do wire (json.dumps compacto) — auditoria e
   reprocesso sem rebaixar a API deles.
4. `bandwidth_gbs` do rig: seed do contrato web §6 (10 valores, matching por
   substring case-insensitive, só gpu_count=1); fora disso NULL.
5. `check.py sync` valida: banco existe; `COUNT(lm_run) >= 4500`;
   `COUNT(lm_model) >= 400`; toda FK de lm_run resolve; `sync_meta` tem as 3
   chaves; nenhum `bandwidth_gbs` fora do conjunto {NULL} ∪ seed; rodar
   sync de novo não muda COUNT(lm_run) (idempotência — o check pode conferir
   comparando com `synced_runs`).

## O que NÃO fazer

- Não paralelizar requests; não baixar leaderboard (models+speed-tests
  bastam ao backend); não transformar métricas (agregação é S4).
- Não apagar o banco a cada sync (upsert, não recreate).

## Verificação

```bash
uv run python -m src.sync_pool     # ~2-4 min com throttle
uv run python scripts/check.py sync
uv run python scripts/check.py all
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f src/sync_pool.py && uv run python scripts/check.py sync
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: shape do wire divergir do contrato web §3; total < 4.500;
>30% dos runs sem bits (tabela insuficiente — humano decide).
