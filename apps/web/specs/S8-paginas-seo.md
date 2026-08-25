# S8 — Páginas SEO (opcional, alto valor)

Depende de: S2, S4. Produz: `scripts/gen-seo.mjs`, `site/p/**/*.html`,
`site/sitemap.xml`, `check.mjs` alvo `seo`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/web/` — trabalhe
> dentro dele. Leia antes: `apps/web/PROMPT-EXECUTOR.md` e
> `apps/web/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte além
> dos listados em "Dados verificados"; o que faltar fica [A DEFINIR]. NUNCA use stub ou `declare const` como workaround de import — importe de verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(web-S8): ...`; mate qualquer servidor que subir.

## Objetivo

Gerar uma página estática por combinação (rig x modelo) com dados do pool —
a cauda longa de busca "can RTX 3090 run <modelo>". Nenhum concorrente tem
página de RESPOSTA por combinação (eles têm leaderboards); esta sessão é o
canal de aquisição orgânica do produto.

## Dados verificados (única fonte de números)

- Conteúdo: exclusivamente `data/derived/pool.json` + `models.json` +
  `hardware.json` (células reais; sem célula -> sem página).
- Design: tokens/componentes do theme.css (S4).

## Saídas exatas

- `scripts/gen-seo.mjs` — gera tudo de uma vez, determinístico.
- `site/p/<rigKey>/<modelSlug>.html` — uma por célula com n >= 2
  (qualquer bits; a página agrega os buckets daquele par).
- `site/p/index.html` — índice agrupado por rig.
- `site/sitemap.xml` — todas as páginas geradas, com raiz [A DEFINIR: domínio
  de produção; usar placeholder `https://REPLACE-DOMAIN/` e listar no ESTADO].
- `check.mjs seo`.

## Spec

1. Template inline no gen-seo.mjs (template literal), uma página contém:
   `<title>Can the {rigLabel} run {displayName}?</title>` + meta description
   com a mediana tok/s; H1 com a pergunta; resposta direta em 1 frase
   ("Yes — community-measured at {median} tok/s ({n} runs)" ou wording de
   tight/no via engine? NÃO — S8 não usa engine: só fatos do pool, sem
   estimativa; se a célula existe, rodou de fato); tabela por bucket de bits
   (bits, mediana tok/s, ttft mediano quando houver, VRAM de pico, máx
   contexto testado, engines); link para as duas jornadas; rodapé com
   ATTRIBUTION + snapshotAt.
2. HTML completo autossuficiente linkando `../../assets/theme.css`; zero JS.
3. Determinismo: mesma entrada -> bytes idênticos; ordenar tudo.
4. `check.mjs seo` valida: >= 50 páginas geradas; sitemap parseia como XML
   (checagem por regex de `<loc>` contando == nº de páginas + índice);
   amostra de 3 páginas contém ATTRIBUTION e não contém "undefined"/"NaN";
   toda página corresponde a célula com n >= 2.

## O que NÃO fazer

- Sem estimativas/extrapolação nestas páginas — só medição real (é a página
  que o Google serve; credibilidade máxima).
- Sem JS, sem fontes externas além das já usadas, sem schema.org por ora.
- Não gerar página para célula n < 2 (single run = evidência fraca demais
  para página de resposta).

## Verificação

```bash
node scripts/gen-seo.mjs
node scripts/check.mjs seo && node scripts/check.mjs all
ls site/p | head
```

## ORÁCULO

- comando: cd apps/web && node scripts/check.mjs seo
- exit esperado: 0 (antes do trabalho: exit 1, alvo desconhecido)

PARE E PERGUNTE se: menos de 50 células com n >= 2 (pool mais raso que o
esperado — humano decide baixar o corte ou adiar a sessão).
