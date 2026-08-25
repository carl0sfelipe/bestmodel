# S3 — Engine de fit e velocidade

Depende de: S2 (schemas; para teste de integração usa `data/derived/` real).
Produz: `site/assets/engine.mjs`, `tests/engine.test.mjs`, `check.mjs` alvo
`engine`.

## Objetivo

Único lugar do site com lógica de decisão: dado um rig e um modelo, responde
"cabe?" (fitClass) e "quão rápido?" (estimateTokS) com base declarada.
Puro, sem DOM, sem fetch — recebe dados como argumento.

## Dados verificados (única fonte de números)

- Assinaturas, regras e constantes: CONTRATO §5 e §6 — literais, sem desvio.
- A fórmula de VRAM (0.15*bits*paramsB + 2.0) é a regra publicada pelo próprio
  localmaxxing ("~0.6 GB por B a 4-bit + 1-4 GB de contexto"); não "melhorar".
- Escala de velocidade entre rigs é LINEAR em bandwidth (decode é
  memory-bandwidth-bound — regra publicada por eles: tok/s ≈ bandwidth ÷
  bytes/token).

## Saídas exatas

- `site/assets/engine.mjs` exportando EXATAMENTE as 6 funções do §5 mais as
  constantes do §6 (re-export permitido).
- `tests/engine.test.mjs` usando `node:test` + `assert` (sem deps), com
  fixtures inline pequenas (2 rigs, 3 modelos, 4 cells inventadas COMO
  FIXTURE — fixtures de teste não são "número de produto", são permitidas e
  ficam só em tests/).
- `check.mjs engine` = roda `node --test tests/` e um smoke de integração:
  carrega `data/derived/*.json` reais, roda `topPicks` para o rig de maior
  runCount e exige >= 1 pick com basis "measured".

## Spec

1. `quantBits`: tabela + fallback do §6. Casos de teste obrigatórios:
   `"Q4_K_M"->4`, `"Q8_0"->8`, `"NVFP4"->4`, `"fp16"->16`, `"IQ3_XS"->3`,
   `"Unsloth-Dynamic-Q4_K_M"->4`, `"weird"->null`.
2. `vramNeededGb`: measured-first (n>=2), fórmula como fallback, null quando
   impossível. Teste: modelo com vramMeasuredGb {"4":{gb:19,n:5}} retorna
   {gb:19, basis:"measured"} e NÃO a fórmula.
3. `fitClass`: thresholds §6. Testes de invariante:
   (a) monotônico em bits — para o mesmo modelo/rig, subir bits nunca melhora
   o fit; (b) monotônico em memGb — mais memória nunca piora o fit.
4. `estimateTokS`: escada do §5. Testes: (a) célula exata n>=3 -> "measured"
   com o valor da mediana; (b) n=1 -> "reported"; (c) sem célula local mas
   com célula em rig de bandwidth conhecido -> valor escalado linearmente e
   basis "extrapolated"; (d) ambos bandwidths null -> null (NUNCA chutar).
5. `topPicks`: só fitClass ok/head; ordenação por (pesoBasis desc, tokS desc);
   teste: um "measured" lento vem antes de um "extrapolated" rápido.
6. Tudo puro: mesmas entradas -> mesmas saídas; sem Date.now(), sem I/O.

## O que NÃO fazer

- Sem heurísticas extras (TTFT, energia, preço): fora do escopo v1.
- Sem cache/memoização; os dados são pequenos.
- Não importar load-data.mjs (engine não conhece fetch).

## Verificação

```bash
node --test tests/
node scripts/check.mjs engine
node scripts/check.mjs all
```

## ORÁCULO

```bash
node scripts/check.mjs engine && echo ORACLE-S3-GREEN
```

PARE E PERGUNTE se: o smoke de integração não achar nenhum pick "measured"
para o rig top (indicaria bug de rigKey entre S2 e S3 — não afrouxe o teste).
