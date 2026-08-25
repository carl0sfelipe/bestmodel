# S4 — Export dos derivados (limpos)

Depende de: S3. Produz: `src/derive_export.py`, alvo `derived`, cópia para o
pack web.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/pool-backend/` — trabalhe
> dentro dele. Leia antes: `apps/pool-backend/PROMPT-EXECUTOR.md` e
> `apps/pool-backend/CONTRATO-GLOBAL.md` (e o contrato web §4 + spec web
> S2-derivacao referenciados). Não invente número, prazo ou fonte além dos
> listados em "Dados verificados"; o que faltar fica [A DEFINIR].
> NUNCA use stub ou `declare const` como workaround de import — importe de verdade.
> Oráculo verde => atualizar ESTADO.md + UM commit `feat(backend-S4): ...`.

## Objetivo

Gerar do SQLite os quatro JSONs derivados que o site consome — mesmos schemas
do pack web — EXCLUINDO dos agregados os runs `impossible`. Este export
substitui, quando presente, o pipeline S1/S2 do pack web (que continua válido
standalone).

## Dados verificados

- Schemas de saída: contrato web §4, literais (parte deste contrato por
  referência). Regras de agregação (medianas por célula, maxContextTested,
  engines únicos, ordenações, 2 casas decimais, determinismo): spec web
  S2-derivacao, itens 2-6 — replicar comportamento, fonte agora é SQL.
- Exclusão por verdict: CONTRATO §6 deste pack (impossible fora; suspicious
  dentro).

## Saídas exatas

- `src/derive_export.py`: executável; escreve
  `out/derived/{hardware,models,pool,stats}.json` e, com flag `--publish`,
  copia os 4 para `../apps/web/data/derived/` (única escrita externa
  permitida — CONTRATO §9).
- `stats.json` ganha um bloco extra (aditivo, não quebra o site):
  `"curation": {excludedImpossible: N, flaggedSuspicious: N, computedAt: iso}`.
- Alvo `derived` no check.py.

## Spec

1. Agregação via SQL (GROUP BY) + pós-processamento em Python; células =
   (rig_key, model_slug, bits) com bits NOT NULL e verdict != 'impossible'.
2. `snapshotAt` = `sync_meta.last_sync_at` (não "agora" — o dado é do sync).
3. Determinismo byte a byte entre duas execuções sem novo sync.
4. `check.py derived` valida: 4 arquivos existem e parseiam; chaves
   obrigatórias do schema web §4 no 1º elemento de cada array;
   `cells >= 500`; toda cell referencia rig/model existentes; nenhum
   NaN/Infinity; `stats.curation.excludedImpossible ==` contagem SQL de runs
   impossible com bits NOT NULL; com `--publish`, os 4 arquivos em
   `../apps/web/data/derived/` são byte-idênticos aos de out/.

## O que NÃO fazer

- Não mudar schema web sem ser aditivo (o site de S5-S7 web não pode quebrar).
- Não recalcular flags aqui (S3 é a dona); não escrever fora de out/ e do
  destino `--publish`.

## Verificação

```bash
uv run python -m src.derive_export
uv run python scripts/check.py derived
uv run python -m src.derive_export --publish
uv run python scripts/check.py all
# se o pack web já tiver check.mjs derived (web S2 feita), rodar também:
cd ../bestmodel-web && node scripts/check.mjs derived; cd -
```

## ORÁCULO

- comando: cd bestmodel-backend && test -f src/derive_export.py && uv run python scripts/check.py derived
- exit esperado: 0 (antes do trabalho: exit 1 no test -f)

PARE E PERGUNTE se: o cross-check com o check.mjs do pack web falhar (schemas
divergiram entre packs — humano arbitra qual contrato corrige).
