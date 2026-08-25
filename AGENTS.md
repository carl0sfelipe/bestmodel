# AGENTS.md — Master Map (bestmodel)

> **bestmodel** ([bestmodel.run](https://bestmodel.run)) is the open
> compatibility engine for local AI — it answers "which model can this machine
> run, how fast, and is it worth it?" from a signed, validated community
> measurement pool. Phase 0 is complete; Phase 1 is planned in
> `docs/backlog.md` + `specs/en/`.

## Read order (do this first)

1. This file (map + golden rules).
2. `README.md` — product overview, quickstart.
3. `docs/architecture.md` — module dependency graph.
4. `docs/findings.md` — numbered calibration findings (open decisions reference these).
5. `docs/backlog.md` — the canonical backlog (tracks A/B/C/D) and open questions.
6. Then the relevant subtree map (every directory has its own `AGENTS.md`).

## Map system (where things live)

Every directory has an `AGENTS.md` acting as its map; the nearest one to your
edit wins. Root → subtree:

| Path | What it maps |
|---|---|
| `docs/AGENTS.md` | Planning docs: architecture, findings, backlog, research |
| `docs/en/deploy.md` | Production runbook: Vercel front + Docker backend, backups, cloud migration, closed-source boundary |
| `specs/en/AGENTS.md` | Executable specs (Phase 0: S00–S12 done; Phase 1+: L01, L02) |
| `infra/AGENTS.md` | Docker stack (ports!), migrations, seed, gate, scripts |
| `packages/AGENTS.md` | Shared Python packages (+ one per package) |
| `apps/AGENTS.md` | Services: public-api, intake-worker (+ one per app) |
| `apps/web/AGENTS.md` | Static site + data pipeline |
| `apps/pool-backend/AGENTS.md` | Pool sync, plausibility curation, local match API |
| `cli/benchmark-probe/AGENTS.md` | The Rust CLI (measurement agent) |
| `cli/comfy-lab/AGENTS.md` | Diffusion vertical tooling |
| `tests/AGENTS.md` | Root-level integration/regression suites |

External-facing LLM entry point: `llms.txt` (root).

## Language & commit rules

- **All code, comments, identifiers, and commit messages: English.**
- Historical build specs under `apps/*/specs/` and `cli/comfy-lab/specs/`
  remain in Portuguese (frozen originals of how those components were built);
  new docs and specs are written in English.
- Commit per completed spec/story with a conventional message
  (`feat(S09): ...`, `docs: ...`).

## Workflow rules

- Specs are self-contained with acceptance commands: make acceptance pass
  before moving on.
- Python runs through `uv`; `make test` is the single test entry;
  `make gate` is the end-to-end gate.

## Golden rules / gotchas (learned the hard way)

1. **Ports**: the stack deliberately avoids common defaults — ours are
   postgres 5434, redis 6380, minio 9002/9003, meilisearch 7701.
   `make check-ports` guards this; `make infra-up` is the safe way up.
2. **Python import layout**: packages use flat modules exposed via pytest
   `pythonpath` (see root `pyproject.toml`); `apps/*/src/__init__.py`
   bootstraps sys.path for direct runs. Do not reintroduce `from src.x import`
   across packages.
3. **Stale processes**: interrupted gate runs leave workers/API alive and they
   will steal stream messages or ports. `pkill -f "src.worker"` before
   debugging queue issues.
4. **uv venv is path-bound**: after moving/renaming the repo,
   `rm -rf .venv && uv sync`.
5. **Cargo workspace**: binaries land in root `./target/debug/`, not per-crate
   dirs.
6. Real hardware numbers are precious: measured data (lab corpus) lives in
   `tests/regression/vram_error_harness.py`; never weaken assertions to make
   tests pass.

## Current status snapshot (keep updated)

- Phase 0: **COMPLETE** (S00–S12 committed; `make gate` green: infra → seed →
  pytest + cargo → CLI signed report → API 202 → worker validated →
  leaderboard; VRAM P50 error ~6%).
- Phase 1: **S13–S20 DONE** (auth; rigs/profiles; claims+voting with frozen
  priors; settle flow + reputation; follows/notifications/feed; share cards;
  web console oracle; embeddable badges + reputation-scaled rate limits).
  L02 social platform feature-complete; CLI --settle-claim shipped
  (B4 loop closed, integration gate PASS). Deployment artifacts live in
  deploy/ (compose prod stack, Caddy edge/tunnel profiles, backup scripts)
  with frontend on Vercel — see docs/en/deploy.md.
  CLI v2 Local Lab (`specs/en/L01-cli-v2-local-lab.md`) planned; social spec:
  `specs/en/L02-social-platform.md`; backlog tracks B/C.
- Open decisions: backlog A1–A6 + roofline threshold calibration (finding F2).
