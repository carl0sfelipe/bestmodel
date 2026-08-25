# S6 — Página goal-first (site/index.html)

Depende de: S2, S3, S4 (S5 recomendada antes, pelos padrões que estabelece).
Produz: `site/index.html`, `site/assets/goal-page.mjs`, `check.mjs` alvo
`page:goal`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/web/` — trabalhe
> dentro dele. Leia antes: `apps/web/PROMPT-EXECUTOR.md` e
> `apps/web/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte além
> dos listados em "Dados verificados"; o que faltar fica [A DEFINIR]. NUNCA use stub ou `declare const` como workaround de import — importe de verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(web-S6): ...`; mate qualquer servidor que subir.

## Objetivo

Portar `prototypes/goal-first.html` (7 cenas scroll-scrubbed) para dados
reais. É a homepage: mad-lib de intenção -> universo -> máquina -> espectro
de fit com quant switcher -> simulação -> 3 recomendações -> visão de sistema.

## Dados verificados (única fonte de números)

- Estrutura do protótipo (verificada no fonte): cena s01 mad-lib com tokens
  `data-k="input|output|machine"`; s02 universo (`#univTotal`, `#univMatch`);
  s03 máquina (schematic SVG + `#rigSelect`); s04 espectro (`#specNodes`,
  eixo won't-run/tight/comfortable/headroom, quant seg `#quantSeg` com
  FP16/Q8/Q6/Q4); s05 simulação (`#simName`, `#vramFill`, `#ctxReach`,
  `#speedNum`); s06 resposta (`#recGrid`, `#modelSearch`); s07 sistema
  (eco SVG, install, "Read how scoring works").
- Números exibidos: só `data/derived/*` + engine.

## Saídas exatas

`site/index.html`, `site/assets/goal-page.mjs`, subcomando `page:goal`.

## Spec

1. Mad-lib (s01): input fixo `text`; output = `text` | `code` (ativos) +
   image/audio/video/embeddings desabilitados com tooltip "no community data
   yet" (§7.6). machine = mesmos topRigs da S5 (componente/select reutilizado).
2. Universo (s02): `#univTotal` = stats.totals.models (copy: "N public models
   speed-tested by the community"); `#univMatch` = modelos da categoria
   escolhida. Canvas de pontos do protótipo mantido, mas a quantidade de nós
   = número real (sem UNIVERSE_FILL sintético — §7.2).
3. Máquina (s03): schematic SVG mantido; labels (gpuLbl/ramLbl/...) refletem
   o rig selecionado (memGb, hwClass, cpu quando existir; ausente -> "—").
4. Espectro (s04): nós = modelos da categoria, posicionados pela fitClass no
   rig/quant atual; quant seg mapeia FP16->16, Q8->8, Q6->6, Q4->4 via
   engine.quantBits-buckets; `#mcMatch`/`#mcOk` = contagens reais.
5. Simulação (s05): modelo em foco = melhor pick atual; VRAM bar e tok/s como
   na S5; ribbon de contexto = "community-tested up to
   {maxContextTested}" com ghost além disso (§7.5); sem dado de contexto ->
   ribbon oculto.
6. Resposta (s06): `#recGrid` = topPicks(rig, models, cells, 3), cards com
   basisBadge e n; `#modelSearch` filtra por displayName/hfId substring sobre
   TODOS os modelos derived (achou mas não cabe -> card com fitLabel "no" e
   sugestão do maior quant que caberia, se houver).
7. Sistema (s07): manter eco SVG e claims genéricos; install block `hidden`
   (§7.3); link "Read how scoring works" -> `#scoring` âncora com 5 linhas
   estáticas resumindo a escada measured/reported/extrapolated (copy nova,
   sem números).
8. Scroll-scrubbing: reaproveitar o mecanismo do protótipo (IntersectionObserver
   /rAF já existentes); não introduzir bibliotecas.
9. `check.mjs page:goal`: arquivo existe; IDs `univTotal, univMatch,
   specNodes, quantSeg, recGrid, modelSearch` presentes; importa engine.mjs e
   load-data.mjs; proibido `const MODELS`, proibida a string "1,247";
   assets referenciados existem.

## O que NÃO fazer

- Não implementar output image/audio/video "só um pouquinho" — desabilitado é
  desabilitado.
- Não recalcular fit fora do engine (a página não sabe fórmulas).
- Não mexer no visual das cenas além da troca de fonte de dados.

## Verificação

```bash
node scripts/check.mjs page:goal && node scripts/check.mjs all
python3 -m http.server 8901 --directory . &
curl -s -o /dev/null -w "%{http_code}" http://localhost:8901/site/index.html  # 200
```

Aprovação visual: fica a cargo do orquestrador pós-batch — registre
"aprovação visual: pendente-humano" no ESTADO.md e siga para o commit.

## ORÁCULO

- comando: cd apps/web && node scripts/check.mjs page:goal
- exit esperado: 0 (antes do trabalho: exit 1, alvo desconhecido)
