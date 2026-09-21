# S45 — `/wall` human-craft (Tabular Spec-Sheet)

> Decision source: `specs/en/L06-human-craft-web.md` D2/D3. Hand-crafts the human
> view of `/wall` (the measured pool) as a spec sheet — lead with the data, not a
> poetic hero — on the locked system from S43. The `?as=` agent twin (L04 S32)
> is untouched.

## Objective

`/wall` reads as a spec sheet for the pool: the data table leads, the hero is a
thin honest frame (not a `page-head` with a `<br/>` headline), every row keeps
its basis and run count, and the page is structurally distinct from home, `/cli`,
and `/claims`.

## Scope

In: the `/wall` human view (`apps/web-next/app/wall/`), Tabular Spec-Sheet
macrostructure on the S43 tokens; de-slop copy; retire the shared `page-head`.
Out: the agent twin (L04 S32 renders `/wall?as=agent` as a `<pre>` table —
untouched); backend; the pool data itself.

## Contract

1. Macrostructure = **Tabular Spec-Sheet**: the pool table is the page; the hero
   shrinks to a one-line honest frame with the snapshot date. Retire the
   `.kicker` + `<br/>` headline ("What the community<br/>actually measures.").
2. The table keeps every column's basis badge and run count; ranking stays
   labelled provisional (honesty ladder).
3. Copy passes the L06/S43 ban-list; headings roman, no mid-headline `<br/>`.

## Rules

Never invent a cell, a tok/s, or a rank — a cell without a source class does not
render (honesty ladder). Never fake data behind a stub that reports success
(anti-phantom; the analogue of "never use `declare const` as a workaround": do
not seed a fake row to fill the table). Reference S43 tokens by name. Do not
touch the `?as=` twin (L04 S32 `/wall` twin oracle must stay green).
- Gate clause: do not invent a number, metric or copy beyond the ones listed in
  Verified data; missing data renders as "no data yet".
- Gate clause: never use declare const, a stubbed success or a fake badge as a
  workaround — implement the real capability.

## Verified data (2026-09-21)

- `/wall` today opens with `page-head` "What the community<br/>actually
  measures." + a `.wall-row` grid at `border-radius:14px` (`app/wall/page.tsx`,
  `app/globals.css:8`).
- L04 S32 renders `/wall?as=agent` as `data-view="agent"` with a `<pre>` table.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`
(`U=http://localhost:3000`).

1. `/wall` serves a human view: `curl -s "$U/wall?as=human" | grep -q 'data-view="human"'`
2. L04 twin still green: `curl -s "$U/wall?as=agent" | grep -q 'data-view="agent"' && curl -s "$U/wall?as=agent" | grep -q '<pre'`
3. Data leads (a real table on the human view): `curl -s "$U/wall" | grep -Eiq '<table|role="table"|wall-list'`
4. Basis preserved: `curl -s "$U/wall" | grep -Eq 'measured|reported'`
5. No mid-headline break / old slop headline gone: `! curl -s "$U/wall" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br' && ! curl -s "$U/wall" | grep -iq 'What the community'`
6. No banned words: `! curl -s "$U/wall" | grep -Eiwq 'delve|leverage|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm'`

## Oráculo

- comando: cd apps/web-next && pnpm install && pnpm build && pnpm start & sleep 8; U=http://localhost:3000; curl -s "$U/wall?as=human" | grep -q 'data-view="human"' && curl -s "$U/wall?as=agent" | grep -q 'data-view="agent"' && curl -s "$U/wall" | grep -Eq 'measured|reported' && ! (curl -s "$U/wall" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br') && ! (curl -s "$U/wall" | grep -iq 'What the community')
- exit esperado: 0 — `/wall` leads with the spec-sheet table, keeps basis, drops
  the `<br/>` headline, and the L04 twin stays green. Before the rework the same
  command fails at the `<br/>`/"What the community" checks — the clean red state.

## Documented hallmark self-critique (implementer fills in the PR)

- Pre-emit six-axis score (each ≥ 3) from the CSS stamp.
- Gates absent: 38a, 46, 47, 48, 54; responsive 320/375/414/768; table uses
  `minmax(0,1fr)` tracks where gridded (gate 50).
- Diversification: Tabular Spec-Sheet differs from home, `/cli`, and `/claims`.

## Dependencies / out of scope

- Depends on: S43 (tokens). Out: the agent twin, backend, the pool data.
