# L04 — Web redesign: dual view + CLI getting-started + social console

> Escalation source: owner, 2026-09-21 ("critical failure — the site has no
> first step for the CLI; the console is ugly and does not feel like a social
> network; I want every page to have a human view and an agent/TUI view, and
> the redesign specs back for ZCode to implement"). This epic is the
> Clarify → Plan output: a decision record plus a right-sized story cluster.
> It is **web-surface only** — signing keys (D4), duels (C2) and
> bestmodel-cloud stay in the HANDOFF as-is and are out of scope here.

This file is the epic umbrella. It carries the numbered decision record and
the map/order of the stories (S32–S36). Each story is a self-contained spec in
`specs/en/` with a mechanical oracle.

## Validation (spot-checked on `main @ 16cf014`, 2026-09-21)

- `/cli` and `/docs` are absent from web-next: `apps/web-next/app/` has no
  `cli/` or `docs/` route directory. Nav (`apps/web-next/app/layout.tsx`) has
  no getting-started entry.
- Phantom installer confirmed: `apps/web/site/index.html:627`,
  `hardware.html:731`, `m/index.html:721` all carry
  `<div class="install" hidden>` with `curl -sSf canirun.it/sh | sh`; the
  command host does not exist and `apps/web/site/llms.txt:28` admits "There is
  no one-line installer yet."
- The verified guide is invisible to humans: `docs/agent-quickstart.md` is
  linked only from `llms.txt` (agent surface).
- Dual view exists only off-prod: the `?as=` mechanism lives in
  `apps/web/site/assets/journey.js` (the divergent GitHub Pages copy), not in
  web-next (prod). web-next pages are human-only.
- Console is utilitarian: `apps/web/console/index.html` is a passkey capture
  form (feed/claim/vote/report/settle) with no social identity; served verbatim
  at `/console/index.html` and wrapped by `apps/web-next/app/console/page.tsx`.
- CLI reality: only `lab` is dispatched today
  (`cli/benchmark-probe/src/main.rs`); `plan`/`report`/`contribute` from
  `specs/en/L01-cli-v2-local-lab.md` are still planned.

## Decision record

Size legend: **epic** (multi-story) · **story** (one dispatchable spec) ·
**line** (backlog one-liner, no spec) · **rejection** (explicitly not done,
with reason).

### D1 — `?as=` becomes a native, server-resolved contract in web-next — **epic → S32**
Decision: dual view is a query param `?as=human|agent`, resolved **server-side**
in web-next (middleware + shared helper), with `User-Agent` as fallback and
`human` as the browser default; the choice only persists when a human explicitly
picks it, mirroring the existing journey.js precedence. Not a separate path,
not Accept-header content negotiation.
Why: `?as=` is already the published contract in `llms.txt`
(`index.html?as=human`); a param is shareable, deterministic and SSR-friendly;
a path fork or header negotiation would double the route table or hide the
choice from links.
Kills: the "dual view only exists in the non-prod Pages copy" divergence — the
mechanism moves into prod.

### D2 — Console is redesigned into a social surface over existing endpoints — **epic → S34**
Decision: "feels like a social network" = a persistent **identity header**
(handle · rig · points · tier), a primary **feed** of claims/runs rendered as
cards with author handle → profile, basis badge and provenance, plus visible
**recognition** (points/tier, "fake caught"). Pure front-end restyle + wiring
to endpoints that already ship (feed scopes, votes, reports, settle, profile,
follows/notifications from S13–S18/S28). No new backend.
Why: the raw material is already in prod (551 claims, leaderboard, track
record, mural, follows, points); the gap is presentation, not data.
Kills: the "ugly, utilitarian, no identity" console.

### D3 — A `/cli` getting-started route, human + agent twin — **story → S33**
Decision: add a first-class `/cli` route in web-next whose single source of
truth is the already-verified `docs/agent-quickstart.md`. It documents only
what the binary does today (build → `benchmark-probe` → `lab`);
`plan`/`report`/`contribute` appear only inside an explicit "not shipped yet"
block, never as runnable commands. A nav entry ("Get started") points to it.
Why: the honest guide exists and was executed clean on 2026-09-18; the failure
is discoverability, and one source prevents drift.
Kills: the `/cli` 404 dead-end and the invisibility of the real guide.

### D4 — Kill the phantom installer slot — **story (folded into S33)**
Decision: remove the three `<div class="install" hidden>` blocks and their
`curl -sSf canirun.it/sh | sh` text; keep `llms.txt`'s honest "There is no
one-line installer yet." web-next must never render an install command that
does not resolve.
Why: shipping (even hidden) a command to a non-existent host violates the
honesty ladder.
Kills: the fake `canirun.it/sh` one-liner.

### D5 — Retire the GitHub Pages divergence — **story → S36**
Decision: `carl0sfelipe.github.io/bestmodel` (built from `apps/web/site`) stops
serving a divergent copy and instead redirects to `https://www.bestmodel.run`;
`apps/web/site` is frozen as an archived visual reference (like
`apps/web/prototypes/`). This runs **after** web-next has agent twins (S35) so
we never delete the only agent-view surface.
Why: two canonical surfaces guarantee drift; the `?as=` mechanism now lives in
prod, so Pages has no unique job left.
Kills: the DIVERGENT Pages copy as a second source of truth.

### D6 — A real one-line installer is a backlog line, not V1 — **line**
Decision: a hosted `install.sh` (e.g. `bestmodel.run/install.sh`) is recorded
in `docs/backlog.md` as future work; V1 documents the from-source build only.
Why: no install script exists to host; promising one now repeats the phantom.
Kills: nothing yet — it prevents re-introducing a fake installer under pressure.

### D7 — Duels and new gamification in the console are rejected for V1 — **rejection**
Decision: duels (C2), DMs, real-time feeds and any points mechanic beyond the
existing points/tier/"fake caught" are out of console V1.
Why: §5 keeps C2 in the HANDOFF; there is no data to feed duels; the rule is
"don't speculate a feature with no data behind it."
Kills: scope creep that would block the social restyle on new backend work.

### D8 — The agent/TUI twin covers ALL prod routes — **story → S35 (depends on S32)**
Decision: after the mechanism lands (S32, which also delivers the reference
twins for `/` and `/wall`), every remaining prod route gets a deterministic
monospace twin under `?as=agent`. Per-route work is parallelizable.
Why: the owner's requirement is "every page"; the mechanism must exist once and
then fan out.
Kills: the human-only nature of web-next pages.

### D9 — `llms.txt` is updated in the same cut as any route/view change — **contract (in S33/S35/S36)**
Decision: every story that adds a route or changes the view contract updates
`apps/web/site/llms.txt` (and its web-next copy if one exists) in the same PR —
a "Routes" section listing each route and its `?as=agent` twin.
Why: `llms.txt` is the contractual agent surface; a route change without a
contract change is a silent break.
Kills: contract drift between the site and its declared agent map.

## Story map

| Story | Title | Size | Depends on |
|---|---|---|---|
| S32 | Server-resolved `?as=` dual view (mechanism + `/` and `/wall` twins) | story | — |
| S33 | `/cli` getting-started route + nav + kill phantom installer + `llms.txt` | story | S32 (for the `/cli` agent twin) |
| S34 | Console as a social surface over existing endpoints | story | — (existing APIs only) |
| S35 | Agent/TUI twin rollout across the remaining prod routes | story | S32 |
| S36 | Retire the Pages divergence (redirect + freeze) | story | S35 |

## Implementation order (for ZCode dispatch)

1. **S32 first** — it is the architectural keystone; S33 and S35 depend on the
   mechanism it introduces.
2. **S34 in parallel with S32** — the console is its own static surface with no
   dependency on the `?as=` mechanism (it is an authenticated interactive app;
   its agent surface is the REST API in `llms.txt`, so it is exempt from the
   `?as=` twin — see S34).
3. **S33 after S32** — the human `/cli` page could ship independently, but its
   agent twin needs S32; keep them in one story to land the contract once.
4. **S35 after S32** — then per-route twin work parallelizes across routes.
5. **S36 last** — only retire Pages once web-next fully covers the agent view.

Parallel lanes: `{S34}` ∥ `{S32 → S33, S32 → S35 → S36}`.

## Rules (apply to every story in this cluster)

- New copy obeys the honesty ladder (measured > reported > extrapolated >
  formula > no data yet) and never invents a metric, a community number, or a
  CLI subcommand that is not dispatched today.
- No new framework: web-next stays Next.js; the console stays its static
  passkey app.
- No backend/API/worker/migration changes — this cluster is web surface only.
  A story whose diff touches `apps/public-api/`, `apps/intake-worker/`,
  `infra/migrations/` or `kernel/` is out of contract.
- Every acceptance criterion is mechanically verifiable (route status,
  `curl | grep`, or `grep` of source). The oracle is the red→green command.
