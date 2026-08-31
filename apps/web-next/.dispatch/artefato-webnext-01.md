---
id: "webnext-01"
schema: 1
status: in-progress
owner: "carlos"
modelo: "cheaperinference/gpt-5.6-luna"
tentativas: 0
bloqueio: false
evidencia: ""
---

# webnext-01 — bestmodel.run v2: o frontend completo em React/Next.js

Você é um engenheiro frontend sênior. Seu diretório de trabalho (CWD) é um
workdir limpo com uma referência completa dentro. Construa AQUI, do zero, o app
Next.js que portA o melhor do protótipo vanilla do bestmodel.run. Você tem
bash: scaffold, npm install e npm run build são SEUS trabalhos.

## Objetivo

App Next.js (App Router, TypeScript) completo, build verde, com as páginas do
protótipo (home, hardware, the wall, página por modelo, track record, mural,
console estático), dados reais verbatim, o MESMO skin (tokens do theme.css) e
uma propriedade que o protótipo não tinha: mobile-first de verdade, zero scroll
horizontal em 360px em TODA página.

## Ordem de boot — LEIA antes de escrever qualquer arquivo

1. `reference/FACTS.md` — os únicos números que você pode citar.
2. `reference/pages/index.html`, `reference/pages/hardware.html`,
   `reference/pages/leaderboard.html`, `reference/pages/track-record.html`,
   `reference/pages/social-preview.html`, `reference/pages/m-index.html` —
   as páginas do dono: narrativa, estrutura, filtros, tom de voz.
3. `reference/assets/theme.css` — a lei visual (tokens e fontes).
   `reference/assets/engine.mjs`, `reference/assets/wall-page.mjs`,
   `reference/assets/hardware-page.mjs`, `reference/assets/load-data.mjs`,
   `reference/assets/ui.mjs` — a lógica de dados que você vai portar.
4. `reference/data/models.json`, `reference/data/pool.json`,
   `reference/data/hardware.json`, `reference/data/stats.json` — os shapes.
5. `reference/p-samples/` — 3 amostras da página por modelo (padrão a portar
   para rota dinâmica).
6. `reference/console/` — app de captura que entra COPIADO, não portado.

Regra do disco: quando a referência e sua memória discordarem, o disco vence.
Ache divergência? Anote em RESULTADO.md e siga pelo disco.

## Dados verificados (o que PODE usar — nada além)

- 626 modelos (592 chat / 34 code), 163 rigs, 1565 células do pool
  (439 measured com n>=3 / 1126 reported), 5830 runs. Top rig: RTX 3090 24GB
  (629 runs). Top model: Qwen3.8-27B-GGUF (201 runs). Fonte dos números:
  `reference/FACTS.md`, derivado por script dos JSONs de `reference/data/`.
- Skin: fundo `#0B0C0E`, âmbar `#E0A458`, fontes Inter / Inter Tight /
  JetBrains Mono — tudo em `reference/assets/theme.css`.
- Basis honesto: célula com n>=3 é measured, senão reported
  (MIN_RUNS_MEASURED = 3, porta de `reference/assets/engine.mjs`).
- URLs: site https://bestmodel.run · API https://api.bestmodel.run
  (em `reference/console/config.js`).

Nao invente numero, nome de modelo, nome de rig, benchmark, prazo ou fonte
alem dos listados em reference/FACTS.md e dos presentes nos JSONs de
reference/data/. Campo que não existe no JSON não é renderizado — não invente
valor para preencher. O mural usa dados de amostra SEMPRE marcados SAMPLE.
NUNCA use declare const como workaround — importe de verdade.

## O que construir (nesta ordem)

1. Scaffold MANUAL (não use create-next-app): `package.json` com
   next@15 + react + react-dom, devDeps typescript e @types; scripts
   dev/build/start/lint conforme o padrão Next. Rode `npm install`.
   Nenhuma outra dependência: SEM Tailwind, SEM UI kit, SEM pacote de ícones
   (SVG inline como no protótipo).
2. Copie VERBATIM (byte a byte, sem editar): `reference/data/*.json` →
   `public/data/derived/` e `reference/console/` → `public/console/`.
   Porte também `reference/pages/llms.txt` → `public/llms.txt`.
3. `lib/engine.ts` — porta de engine.mjs/wall-page.mjs: constante
   MIN_RUNS_MEASURED = 3, loadDerived() dos JSONs, basisOf(cell), join
   células×modelos×rigs, topRigs por runCount, formatadores de número.
4. `app/layout.tsx` + `app/globals.css` — porta do theme.css (MESMOS tokens
   e fontes), viewport metadata, nav consistente: Hardware · The wall ·
   Track record · Mural · Console.
5. `app/wall/page.tsx` — The Wall: ranking com join de células; filtros
   SEPARADOS por dimensão (rig, categoria chat|code, sort por toks/runs)
   — Lei de UX do dono: NUNCA combinar rig e categoria no mesmo seletor;
   badge basis (measured|reported) em toda linha; 60 linhas; link
   "capture / correct →" para /console. Componente cliente para filtros.
6. `app/hardware/page.tsx` — porta de hardware.html: rigs ordenados por
   runCount, cada rig linka para /wall com o rig pré-selecionado.
7. `app/m/[slug]/page.tsx` — página por modelo (padrão de
   `reference/p-samples/`): displayName, categoria, medianas, runs,
   contexto testado; tabela por rig com badge basis;
   generateStaticParams para TODOS os slugs de models.json.
8. `app/page.tsx` — home: narrativa em cenas do index.html (hero com
   número REAL de runs do stats, problema, solução, journey), CTAs para
   /wall e /console.
9. `app/track-record/page.tsx` — escada Contributor/Replicator/Auditor e
   tabela de pontos com rótulo honesto: live ×2/×5 vs proposta ×3
   (a proposta fica MARCADA como proposta, como no protótipo).
10. `app/mural/page.tsx` — porta de social-preview.html mantendo o badge
    SAMPLE visível (é prévia, não dado da API).
11. RESPONSIVIDADE (requisito DURA — é a dor que abriu esta tarefa):
    mobile-first; nenhuma largura fixa > 360px; tabelas largas em container
    com overflow-x:auto ou viram cards no mobile; grids colapsam para
    1 coluna; alvos de toque >= 44px; teste mental página por página a 360px.
    Nota Next: useSearchParams precisa de boundary Suspense senão o build
    falha.
12. SEO: metadata title/description por página; robots; sitemap básico.
13. `README.md` (como rodar) e `RESULTADO.md` (entregue, ficou de fora,
    divergências achadas).
14. `npm run build` verde. Não deixe `npm run dev` rodando no fim.

## Proibições

- `reference/` é read-only: não editar, não mover, não deletar.
- Não commitar node_modules (.gitignore antes do commit).
- Nenhum dado sintético além do mural SAMPLE declarado.

## Barra

- nome: bestmodel.run (protótipo do dono)
- como fetchar: páginas ao vivo em https://bestmodel.run · fontes em
  reference/pages/ e reference/assets/
- como comparar: oráculo abaixo + A/B visual no browser a 360px e desktop

## Oráculo

- comando: test -f package.json && test -f app/layout.tsx && test -f lib/engine.ts && test -f public/data/derived/models.json && test -d app/wall && test -d app/hardware && test -d app/track-record && test -d app/mural && test -d 'app/m/[slug]' && test -f public/llms.txt && grep -q MIN_RUNS_MEASURED lib/engine.ts && grep -qi viewport app/layout.tsx && npm run build
- exit esperado: 0

## Verificação (propriedade do conteúdo, além do oráculo)

- diff -q reference/data/models.json public/data/derived/models.json (e o
  mesmo para pool/hardware/stats) — dados copiados verbatim.
- grep -q '#0B0C0E' app/globals.css && grep -q '#E0A458' app/globals.css
  — skin portado.
- ! grep -qi tailwind package.json — sem dependência proibida.
- grep -c 'generateStaticParams' app/m/[slug]/page.tsx — páginas por modelo
  são estáticas de verdade.

## Passos

1. Boot: ler tudo da ordem de boot (arquivo por arquivo, sem pular).
2. Scaffold + npm install.
3. Dados verbatim + engine.ts.
4. Layout/skin/nav.
5. Páginas na ordem 5–10.
6. Passada de responsividade 360px.
7. SEO + README + RESULTADO.
8. npm run build verde (corrigir até ficar).
9. Commit (mensagem abaixo).

## Commit

Ao final: git add -A && git commit com a mensagem EXATA:

webnext-01: bestmodel.run v2 em Next.js — wall, hardware, páginas por modelo,
home, track record, mural SAMPLE, console estático; dados derivados verbatim;
skin tokens do theme; mobile-first 360px sem scroll horizontal

## Resultado

App Next.js completo no workdir, build verde, commit feito, RESULTADO.md
honesto sobre o que ficou de fora.
