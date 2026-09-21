# S34 — Console as a social surface (identity + feed + recognition)

> Decision source: `specs/en/L04-web-redesign-dual-view.md` D2/D7. The owner's
> core complaint: the console "is ugly and does not feel like a social
> network." This story restyles and re-wires the existing static console into a
> social surface over endpoints that **already ship** — no new backend.

## Objective

The console reads like a small social network for measured local-AI runs: a
persistent identity (handle · rig · points · tier), a primary feed of
claims/runs as cards with author → profile, basis and provenance, votes, and
visible recognition between contributors. It stays the zero-dependency static
passkey app; only presentation and wiring change.

## Contract

1. **Identity header** — `apps/web/console/index.html` + `console.js` +
   `console.css`:
   - When signed in, a persistent profile strip shows `handle`, reputation
     `points` and `tier`, and the signed-in user's public rigs, sourced from
     `GET /v1/users/{handle}` (existing S14 payload: `handle`, `reputation
     {points,tier}`, `rigs[]`, follow counts).
   - A notifications indicator sourced from `GET /v1/notifications`
     (existing S18), with mark-read via `POST /v1/notifications/{id}/read`.

2. **Social feed** — restyle the existing `#view-feed` claim list into cards:
   - Each card shows author `handle` linking to their profile view, the model,
     the number with its **basis badge** (measured/reported/…), provenance
     (source when present), and the current vote tally.
   - Keep the existing scope (`global`/`following`) and sort/status controls;
     `following` already calls `GET /v1/feed?scope=following`. No new query
     params.

3. **Profile view** — a `#view-profile` section rendering
   `GET /v1/users/{handle}`: identity, points/tier, rigs, follow/unfollow via
   the existing `POST /v1/users/{handle}/follow` (S17), and that user's recent
   claims (filter the existing claims list by handle — no new endpoint).

4. **Recognition** — surface what already exists: points/tier on identity and
   author cards; the "fake caught" credit path (S28 reports) stays reachable
   from claim detail; settled claims keep their share-card preview
   (`/v1/cards/claims/{id}.svg`).

5. **Design language** — align `console.css` with the site tokens (dark, Inter +
   JetBrains Mono, terminal soul); keep the honesty-ladder footer verbatim.

## Rules (hard boundaries)

- **No new backend**: the diff touches only `apps/web/console/**`
  (`index.html`, `console.js`, `console.css`, assets). Any call must hit an
  endpoint that exists today (enumerated in "Verified data"). Verified by
  `git diff --name-only` scope + a grep that no new `/v1/...` path string
  appears beyond the known set.
- **Honesty ladder**: every displayed number keeps its basis badge; never
  invent a community metric (no fabricated counts, streaks, or scores).
- **Rejections (D7)**: no duels, DMs, real-time, or new points mechanics.
- Console is exempt from the `?as=` twin: it is an authenticated interactive
  app; its agent surface is the REST API declared in `llms.txt`.

- Ghost ban: never use declare const, stub modules or TODO shims as a workaround — import the real symbol and render the real data.

- Do not invent a number, a community metric, a route or a CLI subcommand beyond what this spec lists; missing data renders as "no data yet", never a guess.
## Verified data (endpoints that already exist — 2026-09-21)

- `GET /v1/users/{handle}` → handle, reputation{points,tier}, rigs[], follow
  counts (`apps/public-api/src/routes/user_route.py`,
  `services/query_user_profile.py`).
- `GET /v1/feed?scope=&sort=`, `GET /v1/claims`, `GET /v1/claims/{id}`,
  `POST /v1/claims/{id}/votes`, `POST /v1/run-claims/{id}/reports`,
  `GET /v1/cards/claims/{id}.svg|.md` — all already called by `console.js`.
- `POST /v1/users/{handle}/follow`, `GET /v1/notifications`,
  `POST /v1/notifications/{id}/read` (`routes/social_route.py`).

## Acceptance (each criterion = one command; static files, no server needed)

1. Identity strip wired to the profile endpoint: `grep -q '/v1/users/' apps/web/console/console.js`
2. Points and tier are rendered: `grep -Eq 'points|tier' apps/web/console/index.html`
3. Feed cards carry the author handle and basis badge: `grep -q 'handle' apps/web/console/console.js` and `grep -q 'basis' apps/web/console/console.js`
4. Notifications wired: `grep -q '/v1/notifications' apps/web/console/console.js`
5. Follow action wired: `grep -q '/follow' apps/web/console/console.js`
6. Honesty-ladder footer preserved: `grep -q 'honesty ladder' apps/web/console/index.html`
7. No backend touched: `git diff --name-only main -- apps/public-api apps/intake-worker infra | grep -q . ; test $? -ne 0`
8. No unknown endpoint introduced: `! grep -oE '/v1/[a-z/_{}-]+' apps/web/console/console.js | sort -u | grep -vE '^/v1/(auth|feed|claims|users|notifications|run-claims|cards)'`

## Oráculo

- comando: bash specs/en/oracles/S34.sh
- The script runs acceptance 1-8 and fails on the first miss.
- expected exit: `0`. Red state before impl: criterion 1 fails (console.js has
  no `/v1/users/` call today).

## Dependencies / out of scope

- Depends on: nothing (existing APIs only) — dispatchable in parallel with S32.
- Out: porting the console into web-next React; any new social endpoint; duels
  (D7); per-user signing keys (HANDOFF D4).
