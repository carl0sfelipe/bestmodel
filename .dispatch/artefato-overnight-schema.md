---
id: "overnight-schema"
schema: 1
status: draft
owner: "carlos"
modelo: "cheaperinference/gpt-5.6-luna"
tentativas: 0
bloqueio: false
evidencia: ""
---

# overnight-schema — o site ganha caixa pra image/audio/video (runs multimodais)

O dono vai popular as categorias vazias (image/audio/video) com runs REAIS
de uma 3090 nesta madrugada. O dado vai chegar como células novas em
`public/data/derived/pool.json` — mas o site NÃO TEM CAIXA: o tipo Cell só
entende tok/s, os intents multimodais estão com `category: null`, e o wall
renderiza "tok/s" hardcoded. Seu trabalho é abrir essa caixa com tipagem e
render honestos. Você NÃO inventa dado nenhum: a única fonte continua sendo
pool.json — células multimodais simplesmente AINDA não existem lá, e todo
estado tem de refletir essa ausência com honestidade.

## Ordem de boot

1. `apps/web-next/lib/engine.ts` — tipo Cell, loadDerived, basisOf, join.
2. `apps/web-next/app/home-client.tsx` — INTENTS (linhas ~19-26), picker,
   verdict.
3. `apps/web-next/app/wall/wall-client.tsx` — rows com tok/s hardcoded.
4. `apps/web-next/RELATORIO.md` — convenções do branch.

## Dados verificados (nada além)

- INTENTS hoje: chat (chat), code (code), image (null), audio (null),
  video (null), vision (null) — em home-client.tsx.
- Cell atual: células de texto com n, tokSOutMedian, tokSPrefillMedian,
  ttftMsMedian, peakVramGbMedian, bits, engines, maxContextTested,
  modelSlug, rigKey (pool.json).
- basisOf: n>=3 = measured, senão reported (MIN_RUNS_MEASURED=3).
- Categorias de modality que o produto reconhece: chat, code, image,
  audio, video, vision.

Nao invente numero, nome de modelo, métrica ou fonte alem dos listados.
Célula multimodal NÃO existe ainda no pool.json — nenhum dado sintético no
app, nenhum fixture. NUNCA use declare const como workaround.

## O que fazer

1. `lib/engine.ts`:
   - Campos OPCIONAIS na célula (quando existirem no JSON): `category`
     ("image"|"audio"|"video"), `imagesPerSec` (n), `audioXReal` (n,
     ×realtime), `videoFramesPerSec` (n), `steps` (n), `resolution`
     (string, ex. "512x512"), `durationS` (n, segundos de clipe/áudio),
     `pipeline` (string, ex. "sdxl-turbo", "whisper-small", "animatediff-
     lightning"), `precision` (string, ex. "fp16").
   - `metricOf(cell)` → `{ value: number; unit: string; label: string } |
     null`: image → imagesPerSec ("img/s"), audio → audioXReal ("×real"),
     video → videoFramesPerSec ("f/s"); célula de texto ou incompleta →
     null.
   - `basisOf` continua igual (vale pra qualquer célula com n).
2. `home-client.tsx`:
   - INTENTS: image → category "image", audio → "audio", video → "video"
     (vision continua null: sem plano de coleta hoje).
   - Os 4 controles continuam SEPARADOS (UX law). Para intents multimodais:
     o controle "quantization" mostra as precision presentes no pool da
     categoria quando houver células, senão fica desabilitado com estado
     honesto; "context floor" NÃO se aplica a multimodal → escondido
     (não desabilitado: ele não existe nessa pergunta).
   - Verdict por categoria: usa metricOf; sem células → o estado vazio
     honesto de hoje ("no data yet"), nunca zero.
3. `wall-client.tsx`: rows renderizam metricOf(cell) (valor + unit + label
   do badge) e caem no tok/s só para células de texto. Badges basis em
   todas as linhas, como hoje.
4. NENHUM dado novo em public/; nenhum mock; nenhum arquivo de fixture.

## Proibições

- Não tocar em: rotas sociais (/claims /submit /profile /mural), console,
  submit, lib/social.ts, components/claim-parts.tsx, sitemap/robots.
- Nenhuma dependência nova; nada de Tailwind.
- Não rode npm run dev; não deixe processo vivo.

## Barra

- nome: wall + home do branch social/react-next (HEAD 5c8d8ae)
- como fetchar: apps/web-next (arquivos acima, no workdir)
- como comparar: oráculo abaixo + estados honestos (sem dado ≠ zero)

## Oráculo

- comando: cd apps/web-next && test -f lib/engine.ts && grep -q metricOf lib/engine.ts && grep -q imagesPerSec lib/engine.ts && grep -q audioXReal lib/engine.ts && grep -q videoFramesPerSec lib/engine.ts && grep -q 'category: "image"' app/home-client.tsx && grep -q metricOf app/wall/wall-client.tsx && npm run build
- exit esperado: 0

## Verificação (além do oráculo)

- ! grep -q 'vision' com category atribuída em app/home-client.tsx —
  vision continua sem categoria.
- grep -q 'no data yet' app/home-client.tsx — honestidade preservada.
- npm run build verde no fim (639+ páginas, zero erro de tipo).

## Passos

1. Boot: ler os 4 arquivos.
2. engine.ts (campos + metricOf).
3. home-client.tsx (categorias + controles por categoria + verdict).
4. wall-client.tsx (metricOf nas rows).
5. Build verde. NÃO commitar — o orquestrador commita (git aqui não tem
   identidade e NÃO deve ser configurada).

## Resultado

Caixa aberta e tipada: quando o pool.json ganhar células multimodais, home
e wall as renderizam com métrica e basis corretos — sem tocar em mais nada.
