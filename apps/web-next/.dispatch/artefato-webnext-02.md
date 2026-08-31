---
id: "webnext-02"
schema: 1
status: in-progress
owner: "carlos"
modelo: "cheaperinference/gpt-5.6-luna"
tentativas: 0
bloqueio: false
evidencia: ""
---

# webnext-02 — perna 2: minerar o round 2 do Claude Design no app que você já construiu

O app Next.js já existe NESTE workdir (perna anterior, mesma lei). Esta perna
adiciona UMA referência nova e pede uma passada de mineração + atualização.
Você está num workdir git; pode haver commit pendente por falta de identidade
git — ignore, o orquestrador commita.

## Ordem de boot — LEIA antes de escrever

1. `RESULTADO.md` (se existir) e o estado atual do app (`ls app/`, `lib/`,
   `public/`) — o que já foi construído é a base, NÃO refaça.
2. `reference/claude-design/` (NOVO nesta perna): `index.html`,
   `hardware.html`, `leaderboard.html`, `track-record.html`, `theme.css`,
   `assets/main.js`, e `data/` (standings, contributor-points).
3. Releia se precisar: `reference/FACTS.md`, `reference/pages/`,
   `reference/assets/theme.css`, `reference/console/index.html`.

## Dados verificados (o que PODE usar — nada além)

- Tudo da perna 1 continua valendo: números SÓ de `reference/FACTS.md` e dos
  JSONs de `reference/data/`; skin = tokens de `reference/assets/theme.css`.
- As categorias de denúncia REAIS da nossa API estão em
  `reference/console/index.html`: numbers_unreal, wrong_hardware, duplicate,
  other (+ estados open/settled_verified/refuted/controversial).
- O Claude Design é referência de ESTRUTURA/UX, não de dado: os JSONs dele
  (`reference/claude-design/data/`) estão PROIBIDOS como fonte de número —
  standings e contributor-points de lá NÃO entram no app.

Nao invente numero, nome, benchmark, categoria de API ou fonte alem dos
listados aqui e nos arquivos de reference/. Melhoria visual do Claude Design
só entra SEM número novo. NUNCA use declare const como workaround — importe
de verdade.

## O que fazer

1. Compare página por página o app atual vs `reference/claude-design/`:
   index, hardware, leaderboard (nosso /wall), track-record. Para cada página,
   decida adotar ou rejeitar cada elemento estrutural DELE que for melhor.
   Registre a tabela adotado/rejeitado + porquê em `RESULTADO.md` (seção nova
   "claude-design mining").
2. Lei de UX inegociável (regressões conhecidas dele, NÃO reintroduzir):
   filtros SEPARADOS por dimensão — nunca rig e categoria no mesmo seletor;
   rigs ordenados por runCount (RTX 3090 no topo), nunca aleatório; categorias
   são chat|code do models.json, nada de "text to text" à parte.
3. Mural (`app/mural`): adote a estrutura do form de denúncia do
   `reference/claude-design/leaderboard.html` (campos, grounds, fluxo), MAS
   com as categorias REAIS da nossa API (numbers_unreal, wrong_hardware,
   duplicate, other) e mantendo o badge SAMPLE — é prévia, não POST real.
   O POST de verdade continua no console copiado.
4. Honesty patterns dele que valem adotar onde couber: fonte de todo número
   sempre o JSON (nunca hardcoded no copy), source_class/basis visível.
5. `npm run build` verde de novo ao final.

## Proibições

- `reference/` inteiro é read-only.
- Nenhuma dependência nova; nada de Tailwind/UI kit.
- Nenhum número novo no app que não venha dos JSONs de `reference/data/`.
- Não rode `npm run dev` no fim; não deixe processos vivos.

## Barra

- nome: bestmodel.run (protótipo do dono) + claude-design round 2
- como fetchar: reference/pages/ e reference/claude-design/ (no workdir)
- como comparar: oráculo abaixo + A/B visual no browser a 360px

## Oráculo

- comando: test -f package.json && test -f app/mural/page.tsx && grep -q numbers_unreal app/mural/page.tsx && grep -qi claude-design RESULTADO.md && npm run build
- exit esperado: 0

## Verificação (propriedade do conteúdo, além do oráculo)

- ! grep -rq standings public/ — dado do claude-design não vazou pro app.
- diff -q reference/data/models.json public/data/derived/models.json —
  dados verbatim continuam intactos.
- grep -c 'claude-design' RESULTADO.md — seção de mineração documentada.

## Passos

1. Boot: estado atual do app + reference/claude-design/ inteiro.
2. Comparação página por página → tabela em RESULTADO.md.
3. Adoções na mural + melhorias estruturais aprovadas.
4. Build verde.
5. Atualizar RESULTADO.md (entregue, ficou de fora, divergências).

## Commit

Mensagem EXATA (o orquestrador resolve a identidade git):

webnext-02: mineração do claude-design round 2 — form de denúncia na mural
(categorias reais da API), melhorias estruturais aprovadas, rejeições
documentadas; build verde

## Resultado

App atualizado, mineração documentada adotado/rejeitado, build verde.
