---
id: "webnext-03"
schema: 1
status: draft
owner: "carlos"
modelo: "cheaperinference/gpt-5.6-luna"
tentativas: 0
bloqueio: false
evidencia: ""
---

# webnext-03 — perna 3: início da mural dividido nas 2 jornadas (intent OU hardware)

Diretiva do dono: a entrada da mural deve DIVIDIR as duas jornadas — por
intent ou por hardware — como portas separadas. Lei de UX inegociável:
intent e hardware NUNCA no mesmo seletor. App já existe neste workdir
(pernas 1–2 entregues e verificadas; build verde, 637 páginas).

## Ordem de boot — LEIA antes de escrever

1. `app/mural/page.tsx` (estado atual: form de denúncia com as categorias
   reais — isso FICA intocado) e `app/globals.css`.
2. `reference/assets/hardware-page.mjs` — o array `INTENTS` do protótipo do
   dono: é a FONTE VERBATIM das opções de intent (ids, nomes, ícones,
   descrições e flags enabled).
3. `reference/data/stats.json` — `topRigs` (rigs por runCount).
4. `reference/FACTS.md` se precisar de números.

## Dados verificados (o que PODE usar — nada além)

- Intents EXATOS do array em `reference/assets/hardware-page.mjs`:
  chat (enabled), code (enabled), image (text → image · diffusion,
  disabled), audio (speech-to-text · text-to-speech, disabled), video
  (disabled), vision (image understanding · VLMs, disabled). Copie nomes,
  ícones e descrições VERBATIM; disabled fica VISÍVEL mas não clicável,
  com estado honesto (nem todos os intents têm dados hoje).
- Rigs: só os `topRigs` de `reference/data/stats.json` (topo: RTX 3090 24GB,
  629 runs), ordenados por runCount.
- Categorias de denúncia continuam as de `reference/console/index.html`:
  numbers_unreal, wrong_hardware, duplicate, other.

Nao invente intent, rig, número, descrição ou fonte alem dos listados e dos
arquivos de reference/. Intent disabled não gera filtro nem dado novo.
NUNCA use declare const como workaround — importe de verdade.

## O que fazer

1. Reestruturar a ENTRADA da `app/mural/page.tsx`: uma seção inicial com
   DUAS portas de jornada lado a lado (empilham no mobile), títulos
   exatos: "Choose your intent" e "Choose your hardware".
   - Porta intent: as 6 opções do array (chat/code clicáveis; as outras 4
     visíveis com estado disabled e por quê — sem dado ainda).
   - Porta hardware: seleção de rig (topRigs, RTX 3090 no topo).
   - As duas portas NUNCA viram um seletor só; escolher numa porta não
     exige nada da outra.
2. A escolha filtra as rows SAMPLE existentes da mural (por intent ou por
   rig conforme a porta escolhida) — rows continuam SAMPLE, nenhuma row
   nova, nenhum número novo.
3. O form de denúncia e as categorias reais FICAM como estão.
4. `npm run build` verde ao final.

## Proibições

- `reference/` read-only; nenhuma dependência nova; nada de Tailwind.
- Não tocar em wall/hardware/home/track-record/console.
- Nenhum número novo no app fora dos arquivos de reference/.

## Barra

- nome: protótipo do dono (journeys) + mural atual
- como fetchar: reference/assets/hardware-page.mjs e app/mural/page.tsx
- como comparar: oráculo abaixo + A/B visual a 360px

## Oráculo

- comando: test -f app/mural/page.tsx && grep -q 'Choose your intent' app/mural/page.tsx && grep -q 'Choose your hardware' app/mural/page.tsx && grep -q 'image understanding' app/mural/page.tsx && grep -q numbers_unreal app/mural/page.tsx && npm run build
- exit esperado: 0

## Verificação (propriedade do conteúdo, além do oráculo)

- grep -c 'Choose your' app/mural/page.tsx — 2 portas, não um seletor só.
- grep -q '629 runs' app/mural/page.tsx — rig do topo vem dos dados reais.
- diff -q reference/data/models.json public/data/derived/models.json —
  dados verbatim intactos.

## Passos

1. Boot (mural atual + INTENTS + stats).
2. Duas portas na entrada com os títulos exatos.
3. Filtro das rows SAMPLE por porta escolhida.
4. Build verde.
5. Atualizar RESULTADO.md (seção perna 3: o que mudou).

## Commit

Mensagem EXATA:

webnext-03: entrada da mural nas 2 jornadas separadas (intent OU hardware,
portas distintas, intents verbatim do protótipo, disabled honesto); build verde

## Resultado

Mural com as duas portas, filtros honestos, build verde, RESULTADO.md atualizado.
