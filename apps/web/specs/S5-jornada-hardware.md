# S5 — Página hardware-first (site/hardware.html)

Depende de: S2, S3, S4. Produz: `site/hardware.html`,
`site/assets/hardware-page.mjs`, `check.mjs` alvo `page:hardware`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/web/` — trabalhe
> dentro dele. Leia antes: `apps/web/PROMPT-EXECUTOR.md` e
> `apps/web/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte além
> dos listados em "Dados verificados"; o que faltar fica [A DEFINIR]. NUNCA use stub ou `declare const` como workaround de import — importe de verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(web-S5): ...`; mate qualquer servidor que subir.

## Objetivo

Portar `prototypes/hardware-first.html` para dados reais: usuário escolhe o
rig -> vê envelope, categorias com contagens reais, catálogo que cabe,
test-drive com velocidade do pool e coorte real ("quem tem esse rig roda X").
É a página mais próxima do produto final — capricho aqui.

## Dados verificados (única fonte de números)

- Estrutura do protótipo (verificada no fonte): cenas `s01` detect (botão
  `#detectBtn`, select `#rigSelect`), `s02` envelope (`#specCard`, campos
  specGpu/specVram/specBw/specCpu/specRam), `s03` pilares (`#pillars`),
  `s04` catálogo (`#catalogGrid`, sorts fastest/most capable/best fit),
  `s05` test drive (`#tdName`, `#tdVramFill`, `#tdSpeed`, preview),
  `s06` coorte (`#topList`, `#statRow`), `s07` final (install + eco SVG).
- Todos os números exibidos: `data/derived/*` via loadDerived() + engine.

## Saídas exatas

- `site/hardware.html` — markup/CSS da página portados do protótipo,
  importando theme.css/ui.mjs/load-data.mjs/engine.mjs e
  `hardware-page.mjs` (toda a lógica da página).
- `check.mjs page:hardware`.

## Spec

1. `#rigSelect`: opções = `stats.topRigs` (8), rotuladas com label real +
   runCount ("RTX 3090 24GB · 611 runs"). Sem rig "auto" mentiroso: o botão
   `#detectBtn` tenta WebGPU (`navigator.gpu.requestAdapter()`) só para
   PRÉ-SELECIONAR o rig mais parecido (matching por substring de vendor) e
   mostra "best guess — confirm below"; sem WebGPU, rola para o select.
2. Envelope (`s02`): memGb, bandwidthGBs (ou "unknown"), hwClass; barras
   proporcionais ao maior valor entre os topRigs. "Save this rig" ->
   localStorage `cir.rig`.
3. Pilares (`s03`): v1 tem 2 categorias reais (chat, code — CONTRATO §4);
   renderizar os pilares image/audio/video/vision DESABILITADOS com
   "no community data yet" (§7.6). Contagem por pilar = modelos da categoria
   com fitClass ok/head no rig selecionado.
4. Catálogo (`s04`): cards dos modelos que cabem (fit ok/head), quant padrão
   4 bits; cada card mostra displayName, paramsB, fitLabel, estimateTokS com
   basisBadge, e n de runs. Sorts: fastest = tokS desc; most capable =
   paramsB desc; best fit = headroom desc. Modelos sem estimativa aparecem ao
   final com "no data yet" (não somem — honestidade §1).
5. Test drive (`s05`): clique no card seleciona; VRAM bar = vramNeededGb /
   usableMemGb; velocidade = estimateTokS.value com contador animado do
   protótipo; sub-copy do protótipo ("based on verified benchmarks from
   2,400+ rigs") vira o REAL: "based on {n} community runs on this exact
   rig" (ou wording de extrapolated). Preview de texto: manter animação do
   protótipo cadenciada pelo tokS estimado.
6. Coorte (`s06`): `#topList` = top 5 modelos por runCount nas cells do rig
   (nome + mediana tok/s + n); `#statRow` = total de runs do rig, engines
   distintas, quant mais comum. Remover claim "14,320 rigs" (§7.2).
7. Final (`s07`): install block `hidden` (§7.3); manter eco SVG; rodapé =
   attributionFooter(stats).
8. `check.mjs page:hardware` valida: arquivo existe; contém os IDs
   `rigSelect, specCard, pillars, catalogGrid, tdName, topList, statRow`;
   importa engine.mjs e load-data.mjs; NÃO contém `const MODELS` nem
   "14,320" nem "2,400+"; assets referenciados existem no disco.

## O que NÃO fazer

- Não reescrever o CSS das cenas (copiar do protótipo, adaptando seletores
  só onde o markup mudou). Não adicionar cenas novas.
- Não usar quant switcher aqui (o protótipo desta jornada não tem; fixa 4
  bits — o goal-first é quem explora quant).

## Verificação

```bash
node scripts/check.mjs page:hardware && node scripts/check.mjs all
python3 -m http.server 8901 --directory . &   # da raiz do repo
curl -s -o /dev/null -w "%{http_code}" http://localhost:8901/site/hardware.html  # 200
```

Aprovação visual: fica a cargo do orquestrador pós-batch — registre
"aprovação visual: pendente-humano" no ESTADO.md e siga para o commit.

## ORÁCULO

- comando: cd apps/web && node scripts/check.mjs page:hardware
- exit esperado: 0 (antes do trabalho: exit 1, alvo desconhecido)
