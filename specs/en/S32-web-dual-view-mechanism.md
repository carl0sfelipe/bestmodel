# S32 — Server-resolved `?as=` dual view in web-next

> Decision source: `specs/en/L04-web-redesign-dual-view.md` D1/D8. This story
> ports the `?as=` reader mechanism from the divergent Pages copy
> (`apps/web/site/assets/journey.js`) into prod (web-next) as a server-resolved
> contract, and ships the reference twins for `/` and `/wall`. It is the
> architectural keystone; S33 and S35 depend on it.

## Objective

Every web-next route can be read as a **human** cinematic view or an
**agent/TUI** monospace twin, selected deterministically by `?as=` (shareable)
with a `User-Agent` fallback, resolved on the server so the correct view is in
the first byte of HTML (no flash, crawler-safe). This story delivers the
mechanism plus two reference implementations (`/` and `/wall`); S35 fans it out
to the rest.

## Contract

1. **View resolver** — `apps/web-next/lib/view.ts`:
   - `export type View = "human" | "agent"`.
   - `export function resolveView(params: URLSearchParams | undefined, ua: string | null, cookie: string | null): { view: View; reason: string }`.
   - Precedence (first hit wins), mirroring journey.js: `?as=`/`?view=` →
     saved cookie (`bm_view`) → known agent UA → search-crawler UA maps to
     `human` → else `human` (browser default). `reason` is one of
     `url|saved|ua|search|default`.
   - Reuse the exact `AGENT_UA` regex from
     `apps/web/site/assets/journey.js` (copy the token list; do not invent new
     agent names). A unit-testable pure function.

2. **Middleware** — `apps/web-next/middleware.ts`:
   - On every request, compute the view with `resolveView` and set request
     header `x-bm-view` for server components to read.
   - Persist to cookie `bm_view` **only** when the view came from an explicit
     `?as=`/`?view=` (reason `url`) — auto-detection is never written, matching
     journey.js.

3. **Layout wiring** — `apps/web-next/app/layout.tsx`:
   - Read `x-bm-view` (via `next/headers`) and set `<html data-view={view}>`.
   - Render a `<ViewToggle>` (a pair of links `?as=human` / `?as=agent`,
     `apps/web-next/app/_components/view-toggle.tsx`) in the header, with the
     active view marked `aria-pressed`.

4. **Agent twin shape** — a shared wrapper
   `apps/web-next/app/_components/agent-view.tsx` renders
   `<main data-view="agent"><pre>…</pre></main>`: deterministic, monospace,
   no animation/IntersectionObserver, dense text tables built from the **same**
   server data the human view uses. Human view renders
   `<main data-view="human">…</main>` (the existing cinematic content).

5. **Reference pages** (this story):
   - `/` (`apps/web-next/app/page.tsx` + `home-client.tsx`): agent twin renders
     the honesty ladder and the pool totals as text; human view unchanged.
   - `/wall` (`apps/web-next/app/wall/…`): agent twin renders the pool cells as
     a fixed-column text table (rig · model · basis · value · n); human view
     unchanged.

## Rules

- Server-resolved only: no `?as=` decision may depend on client JS for the
  initial render (crawlers and `curl` must get the right view).
- The agent twin is data-equivalent to the human view — same numbers, same
  basis labels; it is a re-presentation, never a different dataset.
- Honesty ladder preserved verbatim in both views; no invented numbers.
- Diff stays inside `apps/web-next/**` (plus the `AGENT_UA` copy). No
  backend/API/migration changes.

## Verified data

- `apps/web-next/app/layout.tsx` renders the nav and `<html lang="en">` today —
  no `data-view`.
- `apps/web/site/assets/journey.js` holds the canonical precedence and
  `AGENT_UA` regex (lines ~1–50) to port.
- `apps/web-next/app/page.tsx`/`home-client.tsx` compute pool answers on the
  server already, so the agent twin can reuse the same props.

## Acceptance (each criterion = one command)

Bring the app up once: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`
(serves `http://localhost:3000`).

1. Explicit human: `curl -s "http://localhost:3000/?as=human" | grep -q 'data-view="human"'`
2. Explicit agent: `curl -s "http://localhost:3000/?as=agent" | grep -q 'data-view="agent"'`
3. Browser default is human: `curl -s -A "Mozilla/5.0" http://localhost:3000/ | grep -q 'data-view="human"'`
4. Agent UA flips to agent: `curl -s -A "GPTBot/1.1" http://localhost:3000/ | grep -q 'data-view="agent"'`
5. Crawler stays human: `curl -s -A "Googlebot/2.1" http://localhost:3000/ | grep -q 'data-view="human"'`
6. `/wall` agent twin is monospace text: `curl -s "http://localhost:3000/wall?as=agent" | grep -q 'data-view="agent"'` and `curl -s "http://localhost:3000/wall?as=agent" | grep -q '<pre'`
7. Resolver + middleware exist: `test -f apps/web-next/lib/view.ts && test -f apps/web-next/middleware.ts`
8. Toggle is in the layout: `grep -q 'view-toggle\|ViewToggle' apps/web-next/app/layout.tsx`

## Oracle

- command: `bash specs/en/oracles/S32.sh` (a script committed with this story
  running acceptance 1–8 in sequence; exits non-zero on the first failure).
- expected exit: `0`. Before implementation the same script exits non-zero
  (criterion 2 fails: no `data-view="agent"`) — that is the red state.

## Dependencies / out of scope

- Depends on: nothing (keystone).
- Out: `/cli` (S33), the remaining route twins (S35), Pages retirement (S36),
  console (S34, exempt from `?as=`).
