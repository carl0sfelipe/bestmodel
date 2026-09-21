# S35 — Agent/TUI twin rollout across the remaining prod routes

> Decision source: `specs/en/L04-web-redesign-dual-view.md` D8/D9. S32 delivered
> the `?as=` mechanism plus the reference twins for `/` and `/wall`. This story
> fans the agent twin out to every remaining prod route so the owner's "every
> page has a human view and an agent/TUI view" holds across the site, and
> updates the `llms.txt` route contract.

## Objective

Each remaining web-next route renders a deterministic monospace twin under
`?as=agent` (and via agent UA), data-equivalent to its human view, using the
shared `AgentView` wrapper from S32. The `llms.txt` "Routes" section lists every
route with its `?as=agent` twin.

## Contract

1. **Routes to cover** (console excluded — S34 exemption):
   `/claims`, `/cloud-anchors`, `/hardware`, `/mural`, `/submit`,
   `/track-record`, `/m/[slug]`, `/profile/[handle]`, `/claim/[id]`.
   (`/` and `/wall` already done in S32; `/cli` in S33.)
2. **Per route**: an agent branch that renders the same server data as a
   `<main data-view="agent"><pre>…</pre></main>` table — no animation, stable
   column order, basis labels intact. Reuse `apps/web-next/app/_components/agent-view.tsx`.
3. **Dynamic routes** (`/m/[slug]`, `/profile/[handle]`, `/claim/[id]`): the
   twin renders the specific record's fields as text; a missing record stays a
   404 in both views (no invented record).
4. **Contract** (D9) — `apps/web/site/llms.txt` gains a "Routes" section:
   one line per prod route with its human default and its `?as=agent` twin.

## Rules

- Data-equivalence: the twin shows the same numbers/basis as the human view; it
  is a re-presentation, not a different query. No invented numbers.
- Determinism: no client-only content in the agent branch; `curl` must get the
  full twin.
- Diff limited to `apps/web-next/**` and `apps/web/site/llms.txt`.

- Ghost ban: never use declare const, stub modules or TODO shims as a workaround — import the real symbol and render the real data.

- Do not invent a number, a community metric, a route or a CLI subcommand beyond what this spec lists; missing data renders as "no data yet", never a guess.
## Verified data

- Route inventory from `apps/web-next/app/` (2026-09-21): `claim/[id]`,
  `claims`, `cloud-anchors`, `console`, `hardware`, `m/[slug]`, `mural`,
  `profile/[handle]`, `submit`, `track-record`, `wall`, plus `/` and (from S33)
  `cli`.
- `AgentView`, `resolveView`, middleware and the `data-view` contract are
  delivered by S32.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`.

1. Every listed route serves an agent twin — loop, must print nothing and exit 0:
   ```
   for r in claims cloud-anchors hardware mural submit track-record; do \
     curl -s "http://localhost:3000/$r?as=agent" | grep -q 'data-view="agent"' || echo "MISS $r"; \
   done | grep . && exit 1 || exit 0
   ```
2. Every listed route still serves a human view by default:
   ```
   for r in claims cloud-anchors hardware mural submit track-record; do \
     curl -s "http://localhost:3000/$r" | grep -q 'data-view="human"' || echo "MISS $r"; \
   done | grep . && exit 1 || exit 0
   ```
3. Agent twins are monospace text: `curl -s "http://localhost:3000/claims?as=agent" | grep -q '<pre'`
4. A dynamic route twin renders a real record (pick any live slug from `/m?as=agent`): `curl -s "http://localhost:3000/m/$(curl -s 'http://localhost:3000/wall?as=agent' | grep -oE '[a-z0-9-]+' | head -1)?as=agent" | grep -q 'data-view="agent"'`
5. Contract lists routes: `grep -qi '^## Routes\|Routes' apps/web/site/llms.txt` and `grep -q '?as=agent' apps/web/site/llms.txt`

## Oráculo

- comando: bash specs/en/oracles/S35.sh
- The script runs acceptance 1-5 across the route list and fails on the first
  missing twin.
- expected exit: `0`. Red state before impl: criterion 1 prints `MISS …` for
  the uncovered routes.

## Dependencies / out of scope

- Depends on: S32 (mechanism + `AgentView`).
- Out: console (S34 exemption); Pages retirement (S36); any new data.
