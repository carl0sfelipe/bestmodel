# S4 — UI kit compartilhado

Depende de: prototypes/ (leitura). Produz: `site/assets/theme.css`,
`site/assets/ui.mjs`, `site/assets/load-data.mjs`, `check.mjs` alvo `uikit`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/web/` — trabalhe
> dentro dele. Leia antes: `apps/web/PROMPT-EXECUTOR.md` e
> `apps/web/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte além
> dos listados em "Dados verificados"; o que faltar fica [A DEFINIR]. NUNCA use stub ou `declare const` como workaround de import — importe de verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(web-S4): ...`; mate qualquer servidor que subir.

## Objetivo

Extrair dos protótipos o que é comum às três páginas (tokens, componentes,
carregamento de dados) para que S5/S6/S7 portem cada página sem duplicar nem
divergir. Os protótipos continuam sendo a referência visual; o kit é a parte
compartilhável deles, literal.

## Dados verificados (única fonte de números)

- Tokens de design: CONTRATO §7 (extraídos dos 3 protótipos — conferir no
  fonte, estão no bloco `:root` de cada um; são idênticos entre eles exceto
  variáveis extras do mobile: `--surface-2`, `--surface-3`, `--amber-soft`,
  `--safe-top`, `--nav-h`, `--bottom-h` — incluir todas).
- Componentes repetidos verificados nos protótipos: `.chip` (state rail),
  `.popover`, `.tip`, `.toast`, bloco `.install` com botão copy, `.eco`
  (SVG do ecossistema), footer, `.qbtn` (segmento de quant), badges de fit
  (cores: no=--dim, tight=#C58E52, ok/head=--green — ver `.snode[data-fit]`
  no goal-first.html).
- Links de fontes (Google Fonts): copiar dos protótipos.

## Saídas exatas

- `site/assets/theme.css` — `:root` completo + classes compartilhadas acima,
  copiadas dos protótipos (fonte de verdade: goal-first.html; onde o mobile
  divergir, prefixar com media query ou classe `.m-` sem quebrar desktop).
- `site/assets/ui.mjs` — helpers DOM:

```js
export function el(tag, attrs, children)        // criador de elemento
export function fmt(n, digits)                  // number -> string, "-" p/ null
export function basisBadge(basis)               // -> HTMLElement (cores §7)
export function fitLabel(fitClass)              // -> {text, cssClass}
export function copyButton(text)                // bloco install/copy reutilizável
export function attributionFooter(stats)        // rodapé com ATTRIBUTION + snapshotAt
```

- `site/assets/load-data.mjs`:

```js
export async function loadDerived()
// -> { hardware, models, pool, stats }  (fetch de ../data/derived/*.json,
//    caminho relativo à página; cache em memória; erro -> throw com mensagem)
```

- `check.mjs uikit` valida: 3 arquivos existem; theme.css contém
  `--amber:#E0A458` e `--bg:#0B0C0E`; ui.mjs e load-data.mjs parseiam
  (`node --check`); ui.mjs exporta os 6 nomes acima (import dinâmico).

## Spec

1. Copiar CSS por blocos comentados, com um comentário de origem por bloco
   (`/* from prototypes/goal-first.html */`) — rastreabilidade barata.
2. `loadDerived` resolve caminhos com `new URL("../../data/...", import.meta.url)`
   para funcionar em site/ e site/m/.
3. Nenhuma função do kit conhece o engine; kit = apresentação e dados.

## O que NÃO fazer

- Não criar componentes novos "que vão ser úteis"; só o que está listado.
- Não converter animações scroll-scrubbed para o kit (ficam por página).
- Não usar CSS custom além do que existe nos protótipos.

## Verificação

```bash
node scripts/check.mjs uikit
node scripts/check.mjs all
```

## ORÁCULO

- comando: cd apps/web && node scripts/check.mjs uikit
- exit esperado: 0 (antes do trabalho: exit 1, alvo uikit desconhecido)

PARE E PERGUNTE se: tokens divergirem ENTRE protótipos (fora as variáveis
extras já listadas) — humano decide qual vence.
