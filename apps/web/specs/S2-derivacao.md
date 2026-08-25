# S2 — Derivação (raw -> derived)

Depende de: S1. Produz: `scripts/derive.mjs`, `data/seed/bandwidth.json`,
`data/derived/{hardware,models,pool,stats}.json`, `check.mjs` alvo `derived`.

## Objetivo

Transformar o snapshot cru em quatro JSONs pequenos e estáveis que o site
consome. É aqui que nasce a agregação (medianas por célula rig x modelo x
quant) e a normalização de identidade de hardware/modelo.

## Dados verificados (única fonte de números)

- Schemas de saída: CONTRATO §4, literais. Regras de rigKey/slug/category: §4.
- Tabela quant->bits e seed de bandwidth (10 entradas): CONTRATO §6.
  `data/seed/bandwidth.json` é escrito EXATAMENTE com o JSON do §6.
- Quants mais comuns no pool (2026-08-12): Q4_K_M (2.395 runs), Q8_0 (255),
  NVFP4 (222), Q4_K_XL (167), Q4_0 (149), fp8 (139) — úteis para sanity check.
- Top hardware por runs (2026-08-12): RTX 3090 24GB (~611), RTX 3060 12GB x2
  (~543), RTX 3060 12GB (~517) — o topo de `stats.topRigs` deve ser coerente
  com isso (tolerância: o pool cresce).

## Saídas exatas

Os 4 arquivos derived do CONTRATO §4 + seed + subcomando `derived`.
`data/derived/` é COMMITADO (o site depende dele).

## Spec

1. `derive.mjs` lê `data/raw/*.json`, considera apenas runs
   `status === "APPROVED"` com `tokSOut > 0`.
2. Hardware: agrupar por `rigKey` (regra §4); `label` legível (ex.
   "RTX 3090 24GB", "RTX 3060 12GB ×2", "Ryzen AI Max 395 64GB");
   `memGb` conforme hwClass; `bandwidthGBs` via matching do seed (regra §6:
   substring case-insensitive, só gpuCount=1).
3. Modelos: agrupar por slug(hfId); `paramsB`/`activeParamsB`/`isMoE`/
   `evalScore` vêm de `models.json` quando o hfId existe lá, senão do bloco
   `model` do run (`params`); `medianTokS` = speedStats.medianTokS quando
   disponível, senão mediana dos runs; `vramMeasuredGb[bits]` = mediana de
   `peakVramGb` dos runs daquele modelo naquele bucket (só runs com
   peakVramGb > 0), com `n`.
4. Pool: célula por (rigKey, modelSlug, bits) — bits via `quantBits`
   (implementar aqui como função local espelhando §6; a S3 reimplementa no
   engine do site, os testes comparam com os mesmos casos). Runs com bits null
   não geram célula. Medianas de tokSOut/tokSPrefill/ttftMs/peakVramGb;
   `maxContextTested` = max(contextLength); `engines` = únicos.
5. Stats: totais + top 8 rigs + top 10 modelos por runCount.
6. Determinismo: arrays ordenados (rigs por runCount desc, models por
   runCount desc, cells por rigKey,modelSlug,bits); números com no máx 2
   casas decimais; rodar duas vezes gera bytes idênticos exceto `snapshotAt`.
7. `check.mjs derived` valida: 4 arquivos existem e parseiam; schemas têm as
   chaves obrigatórias do §4 (checar 1º elemento de cada array); nenhum
   `bandwidthGBs` fora do conjunto {null} ∪ valores do seed;
   `cells.length >= 500`; toda cell aponta para rigKey e modelSlug existentes;
   `stats.totals.runs >= 4500`; nenhum NaN/Infinity serializado.

## O que NÃO fazer

- Não completar bandwidth com specs "de cabeça" — fora do seed é null.
- Não descartar rigs pequenos (long tail fica; a UI decide o que destacar).
- Não calcular fit/velocidade aqui (é S3); derived é só agregação factual.
- Não escrever em `data/raw/`.

## Verificação

```bash
node scripts/derive.mjs
node scripts/check.mjs derived
node scripts/check.mjs all      # raw continua verde
jq '.totals' data/derived/stats.json
```

## ORÁCULO

```bash
node scripts/check.mjs derived && echo ORACLE-S2-GREEN
```

PARE E PERGUNTE se: >30% dos runs ficarem sem bucket de bits (tabela §6
insuficiente — humano decide extensão); ou top de stats.topRigs divergir
grosseiramente dos dados verificados acima.
