---
id: "overnight-schema-fix"
schema: 1
status: draft
owner: "carlos"
modelo: "cheaperinference/gpt-5.6-luna"
tentativas: 0
bloqueio: false
evidencia: ""
---

# overnight-schema-fix — 1 erro de tipo no build (refinamento da perna anterior)

Sua perna anterior entregou engine/home/wall, mas o `npm run build` falha com
UM erro de TypeScript. Conserte-o com o menor diff possível.

## Erro exato (npm run build, apps/web-next)

```
Type error: Argument of type '{ rigKey: string; modelSlug: string; bits: number; n: number; tokSOutMedian: number; tokSPrefillMedian: null; ttftMsMedian: number; peakVramGbMedian: number; maxContextTested: number; engines: string[]; } | ... 6 more ... | { ...; }' is not assignable to parameter of type 'Pick<Cell, "category"> & Partial<Pick<Cell, "imagesPerSec" | "audioXReal" | "videoFramesPerSec">>'.
```

## Causa provável (confira no disco)

As células de TEXTO existentes em public/data/derived/pool.json NÃO têm o
campo `category` (ele só existirá nas células multimodais futuras). Seu
`metricOf` em lib/engine.ts exige `Pick<Cell, "category">`, e alguma chamada
(wall/home) passa células cruas do JSON. A assinatura correta aceita célula
SEM category: use `Partial<Pick<Cell, "category" | "imagesPerSec" |
"audioXReal" | "videoFramesPerSec">>` (ou tipo equivalente) e retorne null
quando category está ausente ou não casa com as três modalidades.

## Dados verificados (o que PODE usar — nada além)

- O erro de TypeScript citado acima, verbatim do build.
- `lib/engine.ts` (seu trabalho da perna anterior) e os call sites em
  `app/wall/wall-client.tsx` e `app/home-client.tsx`.
- Células de texto em `public/data/derived/pool.json` não têm `category`.

Nao invente numero, campo, tipo ou fonte alem dos listados. A correção é
de ASSINATURA/GUARD de tipo, não de schema. NUNCA use declare const como
workaround — importe de verdade.

## Verificação

- npm run build verde (639+ páginas) — prova que o tipo fecha de verdade.
- grep -q imagesPerSec lib/engine.ts — os campos criados continuam lá.

## Proibições

- NÃO mude dados em public/, NÃO mude o schema que você criou (campos
  imagesPerSec/audioXReal/videoFramesPerSec/steps/resolution/durationS/
  pipeline/precision permanecem).
- Nenhum outro arquivo além do estritamente necessário.
- Não rode npm run dev; não commitar (orquestrador commita).

## Oráculo

- comando: cd apps/web-next && npm run build
- exit esperado: 0

## Passos

1. Ler lib/engine.ts e o(s) call site(s) apontados pelo erro.
2. Corrigir a assinatura/guard.
3. npm run build verde.
