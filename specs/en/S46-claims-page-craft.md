# S46 — `/claims` human-craft (Feed / Stat-Led)

> Decision source: `specs/en/L06-human-craft-web.md` D2/D3. Hand-crafts the human
> view of `/claims` (the social wall) as a feed of claims with provenance and
> basis — structurally distinct from the pool spec-sheet — on the locked system
> from S43. The `?as=` agent twin (L04 S32) is untouched.

## Objective

`/claims` reads as a feed: each claim is a card with the claimant handle, the
number and its basis, provenance, and the community vote tally — a social
surface, not a `page-head` + generic card grid. Copy is slop-free and the page
is structurally distinct from home, `/cli`, and `/wall`.

## Scope

In: the `/claims` human view (`apps/web-next/app/claims/`), Feed / Stat-Led
macrostructure on the S43 tokens; de-slop copy; retire the shared `page-head`.
Out: the agent twin (L04 S32); the console social surface (L04 S34); backend;
the claims data itself.

## Contract

1. Macrostructure = **Feed / Stat-Led**: a stream of claim cards (handle · model
   · number + basis badge · provenance · vote tally), not a hero + card grid.
   Retire the `.kicker` + `<br/>` headline.
2. Unvalidated claims stay clearly badged (never mixed with measured pool
   numbers); every number keeps its basis (honesty ladder).
3. Copy passes the L06/S43 ban-list; headings roman, no mid-headline `<br/>`.

## Rules

Never invent a claim, a handle, a vote count, or a metric — only render data that
exists (honesty ladder). Never fake a feed entry behind a stub that reports
success (anti-phantom; the analogue of "never use `declare const` as a
workaround": do not seed a fake claim to fill the feed). Reference S43 tokens by
name. Do not touch the `?as=` twin or the console app.

## Verified data (2026-09-21)

- `/claims` today uses the shared `page-head` + card pattern (`app/claims/`);
  the claims/feed data comes from the existing pool + `/v1/feed`/`/v1/claims`
  endpoints (read-only for the human view).
- L04 S32 renders `/claims?as=agent` as `data-view="agent"`.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`
(`U=http://localhost:3000`).

1. `/claims` serves a human view: `curl -s "$U/claims?as=human" | grep -q 'data-view="human"'`
2. L04 twin still green: `curl -s "$U/claims?as=agent" | grep -q 'data-view="agent"'`
3. Feed carries basis badges: `curl -s "$U/claims" | grep -Eq 'measured|reported|unvalidated|claim'`
4. No mid-headline break: `! curl -s "$U/claims" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br'`
5. No banned words / binary contrast: `! curl -s "$U/claims" | grep -Eiwq 'delve|leverage|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm' && ! curl -s "$U/claims" | grep -Eiq "isn't .+ it's|not just .+ but"`

## Oráculo

- comando: cd apps/web-next && pnpm install && pnpm build && pnpm start & sleep 8; U=http://localhost:3000; curl -s "$U/claims?as=human" | grep -q 'data-view="human"' && curl -s "$U/claims?as=agent" | grep -q 'data-view="agent"' && curl -s "$U/claims" | grep -Eq 'measured|reported|unvalidated|claim' && ! (curl -s "$U/claims" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br')
- exit esperado: 0 — `/claims` reads as a basis-declaring feed with no slop
  headline and the L04 twin still green. Before the rework the same command fails
  at the `<br/>` check (the shared `page-head`) — the clean red state.

## Documented hallmark self-critique (implementer fills in the PR)

- Pre-emit six-axis score (each ≥ 3) from the CSS stamp.
- Gates absent: 38a, 46, 47, 48, 54; responsive 320/375/414/768.
- Diversification: Feed / Stat-Led differs from home, `/cli`, and `/wall`.

## Dependencies / out of scope

- Depends on: S43 (tokens). Out: the agent twin, the console (L04 S34), backend,
  the claims data.
