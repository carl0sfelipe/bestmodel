# S43 — Design system + `/` home human-craft

> Decision source: `specs/en/L06-human-craft-web.md` D2/D3/D4. The keystone of
> the human-craft pass: it locks the shared design system (`design.md`/
> `tokens.css`) that S44–S47 adopt and hand-crafts the home page on a Workbench
> macrostructure with the reinstated ecosystem diagram. Human default view only;
> the `?as=` agent twin (L04 S32) is untouched.

## Objective

The home renders as a made-not-generated page: the intent×rig×quant×context
configurator is the hero (Workbench), the honest verdict declares its basis, the
hand-built ecosystem diagram is the craft anchor, and the copy carries no
no-ai-slop patterns — all on a locked token system the rest of the site shares.

## Scope

In: `apps/web-next/design.md` + `tokens.css` (the locked system); rework
`app/page.tsx`/`home-client.tsx`/`globals.css` for the home human view;
Workbench macrostructure; port the archive ecosystem SVG; de-slop home copy;
move nav/footer off N1a/Ft3; hallmark pre-emit six-axis stamp in the CSS.
Out: other routes (S44–S46); the console (L04 S34); the agent twin and `?as=`
mechanism (L04 S32); any backend; heavy motion.

## Contract

1. `apps/web-next/design.md` — the locked system: genre (editorial-technical),
   the token names, the type roles (JetBrains Mono voice-carrier + display
   face), the macrostructure-per-page map from L06, and the copy voice rules
   (the ban-list below). `apps/web-next/tokens.css` — every `--color-*`,
   `--font-*`, `--space-*`, `--text-*`, `--ease-*`, `--radius-*` token; the page
   CSS references tokens by name, never inline raw values (hallmark gate 48).
2. Home rework:
   - Macrostructure = **Workbench**: the configurator + live verdict is the
     hero; retire the `page-head` (kicker + `<br/>` headline + two buttons) and
     the generic 3-card "stats" grid as the page's proof.
   - Reinstate the ecosystem diagram: port the archive SVG node graph
     (`apps/web/site/index.html`) as a hand-built craft element, redrawn to
     current pool data; no invented nodes.
   - Nav off N1a and footer off Ft3 (a mono masthead + statement footer).
   - No mid-headline `<br/>`; headings roman (no italic headers, gate 38a);
     section eyebrows default OFF (the uppercase amber `.kicker`, gate 54).
3. Copy (no-ai-slop): rewrite the home headline and scene copy to drop the
   ban-list patterns; every number keeps its basis label (measured/reported/…).
4. Stamp: the reworked CSS opens with the hallmark pre-emit critique
   (`/* Hallmark · pre-emit critique: P# H# E# S# R# V# · macrostructure: Workbench · … */`),
   all six axes ≥ 3.

## The copy ban-list (grep gate — reused by S44–S47)

Applied to the route's rendered human HTML. Each must return **no match**:
- Mid-headline break: an `<h1>`/`<h2>` containing `<br`.
- Binary contrast: `isn't … it's`, `not just … but`, `it's not … it's`,
  `not a … not a … a`.
- Colon-reveal drama: a heading of the shape `<h_>Noun phrase: lowercase reveal`.
- Banned words (whole-word, case-insensitive): `delve, leverage, utilize,
  facilitate, robust, seamless, elevate, embark, supercharge, harness,
  unlock, realm, tapestry, paradigm, game.?changer, cutting.?edge,
  ever.?evolving, transformative`.
- Throat-clearing openers: `here's the thing, here's what, let me be clear,
  the truth is, the reality is`.

## Rules

Never invent a number, a community metric, a testimonial, or an ecosystem node
that has no data behind it — every displayed number keeps its basis (honesty
ladder). Never fake a capability or a data source behind a stub that reports
success (anti-phantom; the analogue of "never use `declare const` as a
workaround": do not hardcode a fake cell/handle/stat into the page). Do not
inline raw colour/font values — reference locked tokens by name. Do not touch
the `?as=` agent branch, the middleware, or the twins. Do not weaken the L04
S32 home oracle.
- Gate clause: do not invent a number, metric, handle or copy beyond the ones
  listed in Verified data; missing data renders as "no data yet".
- Gate clause: never use declare const, a stubbed success or a fake badge as a
  workaround — implement the real capability.

## Verified data (2026-09-21)

- Home already computes pool answers on the server (`app/page.tsx`,
  `home-client.tsx`); the configurator + verdict exist and declare basis.
- The archive ecosystem SVG lives in `apps/web/site/index.html`.
- Tokens today are inline in `app/globals.css:2` (no `tokens.css` / `design.md`).
- L04 S32 marks the human view `data-view="human"` and the twin `data-view="agent"`.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`
(`U=http://localhost:3000`).

1. Home still serves the human view: `curl -s "$U/?as=human" | grep -q 'data-view="human"'`
2. L04 twin still green: `curl -s "$U/?as=agent" | grep -q 'data-view="agent"'`
3. Locked system exists: `test -f apps/web-next/design.md && test -f apps/web-next/tokens.css`
4. No mid-headline break on home: `! curl -s "$U/" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br'`
5. No binary-contrast / banned words on home: `! curl -s "$U/" | grep -Eiwq 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' && ! curl -s "$U/" | grep -Eiq "isn't .+ it's|not just .+ but|it's not .+ it's"`
6. Basis still declared (honesty intact): `curl -s "$U/" | grep -Eq 'measured|reported|no data yet'`
7. Ecosystem diagram is hand-built inline SVG, not a fake chrome mockup: `curl -s "$U/" | grep -q '<svg' && ! curl -s "$U/" | grep -Eiq 'traffic-light|window-dots|fake-terminal'`
8. Pre-emit critique stamped: `grep -Eq 'Hallmark · pre-emit critique: P[3-5] H[3-5] E[3-5] S[3-5] R[3-5] V[3-5]' apps/web-next/app/globals.css`

## Oráculo

- comando: cd apps/web-next && pnpm install && pnpm build && pnpm start & sleep 8; U=http://localhost:3000; test -f design.md && test -f tokens.css && curl -s "$U/?as=human" | grep -q 'data-view="human"' && curl -s "$U/?as=agent" | grep -q 'data-view="agent"' && ! (curl -s "$U/" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br') && ! (curl -s "$U/" | grep -Eiwq 'delve|leverage|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm') && curl -s "$U/" | grep -Eq 'measured|reported|no data yet'
- exit esperado: 0 — the home serves a human view with the locked system, no
  slop copy, basis intact, and the L04 twin still green. Before the rework the
  same command fails at the `test -f design.md`/`tokens.css` check (the locked
  system does not exist yet). Amendment note: the home today splits its
  headlines with italic `<em>`, not a literal `<br/>` (gate 38a is the red
  pattern here), and ships the per-word stagger reveal and the generic 3-card
  stats grid this story retires — the red state is the missing system files,
  not a `<br/>` grep.

## Documented hallmark self-critique (implementer fills in the PR — no mechanical oracle)

- Pre-emit six-axis score (Philosophy, Hierarchy, Execution, Specificity,
  Restraint, Variety), each ≥ 3, pasted from the CSS stamp.
- Named gates confirmed absent: 38a italic headers, 46 invented metrics, 47
  re-drawn chrome, 48 mid-render tokens, 54 tag-left header; responsive 34/49–53
  at 320/375/414/768px.
- Diversification: the home Workbench macrostructure differs from S44–S46.

## Dependencies / out of scope

- Depends on: nothing (keystone). Out: other routes, console, agent twin,
  backend, motion.
