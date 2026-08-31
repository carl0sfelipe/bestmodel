# RELATÓRIO — rede social de captura em React/Next

Branch `social/react-next`, em `apps/web-next`. Seis commits pequenos.
Build verde: **639 páginas** (626 SSG de modelo intactas + 13 rotas).

---

## O que foi feito

### MISSÃO A — homepage com a cara do prod

`app/page.tsx` (servidor) + `app/home-client.tsx`. Porta a narrativa em cenas do
index do CanIRunIt: overline numerado, hero com revelação palavra a palavra,
`.scene-reveal` por IntersectionObserver, mono em todo dado, âmbar no acento.

O seletor goal-first tem **quatro controles separados** — intent, máquina,
quantização, contexto. Nenhum é fundido, cada um tem seu próprio grupo rotulado.
Os 6 intents do protótipo estão lá; chat e code ativos, image/audio/video/vision
visíveis e honestamente desabilitados ("no data"). Quantizações sem célula
testada aparecem desabilitadas — a ausência é informação.

**Decisão de arquitetura:** o join roda no servidor contra o pool real e manda
um índice de respostas de 34 KB em vez do `pool.json` de 380 KB. First Load JS
da home foi de 105 → 108 kB. Toda resposta é uma célula `measured` ou
`reported`; combinação sem célula renderiza "no data yet".

### MISSÃO B — as quatro rotas sociais

| Rota | O que entrega |
|---|---|
| `/claims` | O Wall. `source_url` é o herói de cada linha (chip âmbar "found on reddit.com" linkando fora). Badges por status. Cross-signal do engine ao lado do número alegado, nunca somado. Tally como barra de margem. Filtros: status e ordenação em grupos separados. Estado vazio obrigatório. |
| `/claim/[id]` | Figuras grandes em mono, origem, cross-signal, votos, report de 5 categorias em `<dialog>` nativo, bloco settle com comando copiável. Banners para refuted/verified/retracted. 404 tratado. |
| `/submit` | Duas portas separadas — "I found it online" (source_url obrigatória) e "I ran it myself" (opcional). Sem token o form renderiza desabilitado com CTA único pro console. Erro da API mostrado verbatim. |
| `/profile/[handle]` | Reputação, follow, rigs só `is_public`, escada Contributor → Replicator → Auditor com a copy congelada. Degrau não concedido lê "not yet" — nunca some. 404 tratado. |

`lib/social.ts` carrega o contrato; `components/claim-parts.tsx` os componentes
compartilhados. Um campo que a API não mandou **não renderiza** — a regra de
"nenhum número inventado" é estrutural, não questão de cuidado.

---

## Divergências encontradas (disco vence)

**D1 — o path do report no brief está errado.** O brief diz
`POST /v1/claims/{id}/reports`. A API real monta em
`POST /v1/run-claims/{claim_id}/reports`
(`apps/public-api/src/routes/report_route.py:26`). Seguido o disco — o path do
brief teria dado 404 em todo report. Validei os outros oito endpoints contra o
código: **todos conferem** (create/browse/detail de claims, verdict
`plausible|impossible`, `CLAIM_SORTS`, as 5 `REPORT_CATEGORIES`, cap de 1000 em
`reason_detail`, `FAKE_CAUGHT_POINTS = 5` — a copy "+5 points" está correta).

**D2 — não existe rewrite same-origin `/v1/*` neste repo.** `deploy/Caddyfile` só
proxia `api.bestmodel.run → api:8000`. Implementei base `""` como mandado, mas
sobrescrevível por `NEXT_PUBLIC_API_BASE` sem mudar código. **Confirme antes de
subir**, senão toda chamada social bate em 404 no próprio host.

**D3 — colisão de nome "The wall".** A rota `/wall` já existente se chamava "The
wall" e mostra células do pool. Renomeei só o **rótulo do nav** para "Pool" (o
que ela sempre foi) e "The wall" agora aponta pra `/claims`. Rota, conteúdo e
metadata de `/wall` intactos. É uma palavra pra reverter se você discordar.

**D4 — `model_release_id`: mando o `hfId`.** É o identificador canônico e cabe no
cap de 128. Se a API espera o `slug`, é uma linha em `app/submit/page.tsx`.

**D5 — shape de `badges` é opaco no contrato.** A escada casa por substring do
nome do degrau em qualquer string do badge. Conservador: na dúvida marca
"not yet" em vez de conceder um nível que a API não deu.

**D6 — campos do create que não uso:** `rig_slug` e `inference_runtime_id`
existem no `CreateRunClaimRequest` e ficaram de fora do form.

**D7 — o `globals.css` existente é desktop-first** (`@media(max-width:760px)`).
Meus blocos novos são mobile-first (min-width). Não unifiquei os dois para não
mexer no layout das páginas existentes.

**D8 — lacunas pré-existentes que corrigi** (aditivo, sem remover regra):
o projeto não tinha **nenhum** `:focus-visible` — teclado só tinha o anel do
browser; `overflow-x` era `hidden` em vez de `clip`; links do nav mediam 17px e
o wordmark 18px, ambos abaixo do piso de 44px; `.rig-option` da mural em 42px.

---

## O que ficou de fora

- **Basis `extrapolated` na home.** Não portei o escalonamento por bandwidth do
  `engine.mjs`. Combinação sem célula real mostra "no data yet" em vez de uma
  estimativa. É o degrau honesto de baixo da escada, mas é menos cobertura.
- **Nome de exibição do modelo no Wall.** Renderizo o `model_release_id` cru —
  é a verdade da API e já é legível. Resolver pra `displayName` custaria ~55 KB
  de mapa no cliente numa página que hoje tem zero linhas.
- **`/profile` sem handle no nav.** Perfis são por handle; sem sessão não há
  handle pra linkar. Chega-se a eles clicando no autor de um claim.
- **Deep-link de filtros no Wall** (status/sort na URL). Estado é local.
- **Teste automatizado.** Não há runner de teste em `web-next`; o audit abaixo
  foi medido, mas não está versionado como suíte.

---

## Audit medido (Chromium headless via WebDriver, zero dep nova)

Não é inspeção visual: cada rota foi carregada e medida em 360px e 1440px.

| Verificação | Resultado |
|---|---|
| Scroll horizontal da página | **0 rotas** — `scrollWidth === clientWidth` em 20/20 |
| `overflow-x` em html **e** body | `clip` / `clip` em todas |
| Alvos de toque < 44px | **0** (após correção; achou nav 17px e wordmark 18px) |
| Texto clicável quebrando em 2 linhas | **0** (medido por `getClientRects().length`) |
| Regressão nas rotas existentes | **0** — `/wall`, `/hardware`, `/mural`, `/track-record`, `/m/[slug]` limpas |
| Build | verde, 639 páginas |

**20/20 limpo.** Conteúdo largo (tabelas de `/track-record` e `/m/[slug]`, e o
nav no mobile) rola dentro do **próprio** container — a página não rola.

### Disciplina aplicada

Um controle por dimensão em toda página que filtra. Oito estados nos elementos
interativos (default/hover/focus/active/disabled/loading/error/success). Borda
de campo com largura constante entre estados e slot de outline pré-reservado —
sem layout shift no foco. Label acima do campo, helper com altura reservada,
erro substituindo o helper. Validação no blur. `<dialog>` nativo pro modal.
Hover dentro de `@media (hover:hover)`. `prefers-reduced-motion` respeitado.
Nenhum token existente redefinido — só nomes novos (motion, focus, field height).

---

## Para subir

1. Confirmar o roteamento de `/v1/*` (D2) ou setar `NEXT_PUBLIC_API_BASE`.
2. Confirmar se `model_release_id` é `hfId` ou `slug` (D4).
3. Decidir se o rótulo "Pool" para `/wall` fica (D3).
