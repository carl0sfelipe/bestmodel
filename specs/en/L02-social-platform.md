# L02 — Social Platform (accounts, rigs, claims, votes, virality)

> Phase 1+ story cluster. Language policy: Phase 1 specs are written in English.
> Builds on Phase 0 deliverables S00–S12 (signed benchmark pool, anti-fraud
> intake, roofline kernel, trust system, leaderboard) and consumes Track B/C of
> `docs/backlog.md` as product direction. Coexists with L01 (CLI v2 Local Lab):
> L01 feeds measured runs, L02 wraps every number in a social loop.

## Objective

Turn the compatibility engine into a **social network for local AI
performance**: people register, claim their rigs, assert runs ("claimed"
track), challenge each other's numbers with community plausibility voting,
convert claims into verified runs through the CLI, and share result cards that
bring new members in. Every social object stays anchored to the honest-numbers
ladder (`measured > reported > extrapolated > formula > no data yet`) — the
feed is the flywheel's intake, never a replacement for it.

Positioning: whichllm/modelfit are read-only catalogs; r/LocalLLaMA has the
arguing but no measurement protocol. Nobody owns **"prove it" as a game**.

## User experience (target)

```text
/                       feed: trending claims, fresh verified runs, biggest upsets
/u/<handle>             profile: rigs, claims, verified runs, badges, reputation
/rigs/<slug>            one rig: full topology + everything measured on it
/m/<model>/on/<gpu>     SEO catalog page (exists) + discussion thread
/cards/<claim>          auto-generated share card (PNG/markdown), links back
```

Core loops:

1. **Claim → vote → prove**: user asserts a run without proof → community
   votes plausible/impossible (priors from our own predictors shown inline)
   → disputed claim becomes a duel → settled by a signed CLI run → both
   parties earn reputation.
2. **Register rig → get matched**: a registered rig unlocks personalized
   "you can run X at Y tok/s" pages and the plan/lab entry points.
3. **Card → virality**: every verified run mints a shareable card sized for
   X/Reddit/Discord; each card links back to its pool cell.

## Data model (migration 0005+, additive)

| Table | Purpose |
|---|---|
| `app_user` | handle, display name, auth identity (passkey / GitHub OAuth), created_at. No emails required for v1. |
| `user_reputation` | points + tier (mirrors trust levels L0–L4); events append-only (`reputation_event`) |
| `rig` | owner FK, nickname, slug, hardware fingerprint JSON (same topology shape as CLI detection), optional public flag |
| `run_claim` | claimant FK, rig/model/quant/runtime/context refs (catalog FKs nullable until bound), claimed metrics jsonb, status: open/settled_verified/refuted/retracted, prior snapshot (roofline range at creation time, frozen) |
| `claim_vote` | voter FK, claim FK, verdict (plausible/impossible), weight = f(voter reputation), unique(voter, claim) |
| `follow` | follower FK, followee FK (users and rigs both followable) |
| `badge` | awarded badges (first_verified_run, giant_killer, pool_contributor_100h, ...) |

Rules:

- Claims are **never mixed into validated leaderboards** (Track B2 decision).
- Vote weight is bounded; a single whale cannot flip a verdict alone.
- Prior snapshot is frozen at claim creation — no rewriting history when
  predictors improve.
- Verified conversion links `run_claim.id` ↔ `benchmark_run.id` (one-click
  "prove it" pre-filled lab session, Track B4).

## Service surface

Extend `apps/public-api` (same deploy unit initially):

- `POST /v1/auth/*` — passkey/GitHub sessions, bearer tokens for agents
- `POST /v1/rigs` · `GET /v1/rigs/{slug}` · `GET /v1/users/{handle}`
- `POST /v1/claims` · `GET /v1/claims?status=open&sort=controversial`
- `POST /v1/claims/{id}/votes` · `POST /v1/claims/{id}/settle` (attach signed run)
- `GET /v1/feed?trending=week` — ranked by vote velocity + upset factor
- `GET /v1/cards/{claim}.png` — server-rendered share card (also `.svg`, markdown)

Frontend: static-first like `apps/web`; interactive console (browse/vote/
claim without a terminal, Track C6) ships as a thin JS layer over these
endpoints — no SPA framework unless a spec justifies one.

## Anti-abuse

- Claim rate limits scale with reputation; new accounts get low ceilings.
- Vote rings detected by the same robust z-score machinery as the intake
  worker (`apps/intake-worker` reuse, not reimplementation).
- Refuted claims stay visible, badged — deletion is for spam only.
  Honest-but-wrong is not a crime here; faked evidence is.

## Delivery order

| Step | Story | Acceptance gate |
|---|---|---|
| S13 | Migration 0005 + auth (passkey first) | DONE: migrations 0005+0006 applied; 15 auth suites green; real-PG constraint smoke passed |
| S14 | Rigs + profiles + catalog binding | profile page renders from API fixtures |
| S15 | Claims + priors snapshot + voting | vote margin math property-tested |
| S16 | Settle flow (claim → signed run conversion) | e2e: claim → CLI run → settled, rep credited |
| S17 | Feed + trending + share cards | card PNG matches template golden file |
| S18 | Web console (C6) on top of the API | oracle: full loop without touching a terminal |

## Boundary with the commercial side (explicit)

Managed/hosted inference (rented GPUs, optimized containers) is operated under
a separate proprietary codebase. This repository integrates with it exclusively
through public HTTP APIs behind an opt-in `cloud` module: the open platform
never requires it, and removing it must leave every social/engine feature
functional. Any provider-specific logic belongs to the proprietary side.
