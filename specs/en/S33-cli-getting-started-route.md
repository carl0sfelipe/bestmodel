# S33 — `/cli` getting-started route + nav + kill phantom installer

> Decision source: `specs/en/L04-web-redesign-dual-view.md` D3/D4/D9. Fixes the
> critical failure that triggered the escalation: a human landing on the site
> has no first step for the CLI. Adds a `/cli` route sourced from the verified
> guide, wires nav, removes the phantom installer, and updates the `llms.txt`
> contract in the same cut.

## Objective

A human (or their agent) reaches a working, honest getting-started for the CLI
from the site's navigation, promising only what the binary does today
(build → `benchmark-probe` → `lab`). The invisible-but-good
`docs/agent-quickstart.md` becomes the single rendered source, and the fake
`curl … canirun.it/sh` slot is deleted.

## Contract

1. **Route** — `apps/web-next/app/cli/page.tsx` (SSR):
   - Renders `docs/agent-quickstart.md` as the **single source of truth** (read
     the markdown at build/render time and render to HTML; do not re-type the
     steps into JSX). A thin human intro/hero may wrap it.
   - `plan` / `report` / `contribute` appear **only** inside an explicit
     "Not shipped yet" block (labelled in-construction), never as runnable
     commands. Only `benchmark-probe`, `lab`, the from-source build, and
     `make agent-smoke` are shown as runnable.
   - Dual view (from S32): `?as=human` is the narrated page, `?as=agent` is the
     monospace twin (the raw quickstart commands as a `<pre>` block).

2. **Navigation** — `apps/web-next/app/layout.tsx`:
   - Add `<Link href="/cli">Get started</Link>` to the primary nav (placed
     first, before "The wall").

3. **Kill the phantom installer** (D4):
   - Remove the `<div class="install" hidden>` block (and its `installCmd`
     span carrying `curl -sSf canirun.it/sh | sh`) from
     `apps/web/site/index.html`, `apps/web/site/hardware.html`,
     `apps/web/site/m/index.html`. Remove now-dead `installCmd`/copy-button JS
     if it references only that slot.
   - web-next must not introduce any install one-liner.

4. **Contract update** (D9) — `apps/web/site/llms.txt`:
   - Add `/cli` to a human-facing "Get started" pointer.
   - Keep the honest line "There is no one-line installer yet."
   - Add `/cli?as=agent` to the routes/agent map.

## Rules

- Honesty ladder: the page documents no subcommand that is not dispatched in
  `cli/benchmark-probe/src/main.rs` today. Cross-check against that file.
- One source: the human steps must come from `docs/agent-quickstart.md`; if the
  guide changes, the page changes with it (no duplicated command text in JSX).
- Diff limited to `apps/web-next/app/cli/**`, `apps/web-next/app/layout.tsx`,
  the three `apps/web/site/*.html` files, their dead installer JS, and
  `apps/web/site/llms.txt`.

## Verified data

- `docs/agent-quickstart.md` was executed on a clean checkout 2026-09-18 and
  carries the `make agent-smoke` self-check.
- Only `lab` is dispatched today (`cli/benchmark-probe/src/main.rs`);
  `plan`/`report`/`contribute` are planned in
  `specs/en/L01-cli-v2-local-lab.md`.
- Phantom slot locations: `apps/web/site/index.html:627`, `hardware.html:731`,
  `m/index.html:721`.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`.

1. Route exists (was 404 → red before): `test "$(curl -so /dev/null -w '%{http_code}' http://localhost:3000/cli)" = 200`
2. It documents the real CLI: `curl -s http://localhost:3000/cli | grep -q 'benchmark-probe'` and `curl -s http://localhost:3000/cli | grep -q 'agent-smoke'`
3. Unshipped subcommands are quarantined, not runnable: `curl -s http://localhost:3000/cli | grep -iq 'not shipped\|in construction'`
4. Nav points to it: `grep -q '"/cli"' apps/web-next/app/layout.tsx`
5. Agent twin (needs S32): `curl -s "http://localhost:3000/cli?as=agent" | grep -q 'data-view="agent"'`
6. Phantom installer is gone: `! grep -rn 'canirun.it/sh' apps/web/`
7. Contract keeps the honest line: `grep -q 'no one-line installer yet' apps/web/site/llms.txt`
8. Contract lists the new route: `grep -q '/cli' apps/web/site/llms.txt`

## Oracle

- command: `bash specs/en/oracles/S33.sh` (runs acceptance 1–8; fails on first
  miss).
- expected exit: `0`. Red state before impl: criterion 1 returns `404`.

## Dependencies / out of scope

- Depends on: S32 (for criterion 5, the agent twin). Criteria 1–4, 6–8 are
  independent and can be verified before S32 lands.
- Out: a real hosted installer (D6, backlog line); rendering the full
  `docs/en/` tree (only `/cli` is in scope here).
