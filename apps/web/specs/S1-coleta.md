# S1 — Coleta (harvest da API pública)

Depende de: nada. Produz: `scripts/harvest.mjs`, `scripts/check.mjs` (alvo
`raw`), `data/raw/*.json`, `.gitignore`.

## Objetivo

Congelar um snapshot local completo do pool público do localmaxxing
(speed-tests, models, leaderboard) em JSON cru. Tudo que o site mostra nasce
deste snapshot — nunca de chamadas ao vivo no browser.

## Dados verificados (única fonte de números)

- Endpoints, envelopes, throttle e etiqueta: CONTRATO §3. Em particular:
  lista de runs vem no campo `speedTests` (a doc deles diz `benchmarks` — está
  errada; siga o contrato).
- Total de speed-tests em 2026-08-12: 5.026. Models cadastrados: ~687.
- Paginação: `limit` máx 100 em /speed-tests (docs deles); /models aceita
  limit=200. /leaderboard: `limit` máx 200.

## Saídas exatas

- `scripts/harvest.mjs` — executável via `node scripts/harvest.mjs`.
- `data/raw/speed-tests.json` — `{ fetchedAt, total, speedTests: [...] }`
  (concatenação de todas as páginas).
- `data/raw/models.json` — `{ fetchedAt, models: [...] }`.
- `data/raw/leaderboard.json` — `{ fetchedAt, total, rows: [...] }`.
- `scripts/check.mjs` — subcomando `raw`.
- `.gitignore` com `data/raw/` e `.DS_Store`.

## Spec

1. `harvest.mjs`: para cada endpoint, loop de paginação por offset até cobrir
   `total` (speed-tests, leaderboard) ou até página vazia (models). Respeitar
   `THROTTLE_MS` entre requests; User-Agent do contrato; retry 2x com backoff
   2 s em não-200; abortar com exit 1 e mensagem clara se um retry final falhar.
2. Escrever cada arquivo de uma vez ao final (nada de append parcial); incluir
   `fetchedAt` ISO.
3. Log de progresso em stdout: uma linha por página
   (`speed-tests 1200/5026`), texto puro.
4. `check.mjs raw` valida: os 3 arquivos existem; `speedTests.length >= 4500`;
   `speedTests.length === total` do próprio arquivo; `models.length >= 600`;
   primeiro registro de cada arquivo contém as chaves do CONTRATO §3
   (`model.hfId`, `hardware.hwClass`, `engine.quantization`, `tokSOut`,
   `status`); todo `status === "APPROVED"` OU o check imprime contagem de
   não-aprovados (eles só servem aprovados no endpoint público; se aparecer
   outro status, conte e siga — a S2 filtra).

## O que NÃO fazer

- Não normalizar/transformar nada aqui (isso é S2). Raw = fiel ao wire.
- Não paralelizar requests; não baixar imagens/marketplace; não usar
  /api/agent-context (só GET dos 3 endpoints do contrato).
- Não commitar `data/raw/` (gitignored) — o commit da sessão leva scripts,
  gitignore e ESTADO.

## Verificação

```bash
node scripts/harvest.mjs          # ~1-3 min com throttle
node scripts/check.mjs raw
```

## ORÁCULO (vermelho antes, verde depois)

```bash
node scripts/check.mjs raw && echo ORACLE-S1-GREEN
```

PARE E PERGUNTE se: total retornado < 4.500; shape divergir do CONTRATO §3;
qualquer endpoint responder 4xx/5xx após retries.
