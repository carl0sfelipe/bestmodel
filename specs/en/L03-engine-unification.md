# L03 — Engine Unification (port epics 1–5 from the engine lineage)

> Phase 1 spec. Strategic decision record: `docs/direction-2026-08-28.md` (D1).
> The private engine lineage (`carl0sfelipe/CanIRunIt`, local clone
> `~/Work/CanIRunIt`) built epics 1–5 on top of the same S00–S12 base this
> monorepo was derived from: ComfyUI adapter, recipe schema, `canirunit
> suggest` with confidence + cross-GPU roofline transfer, harvesters with a
> review queue, and the reported-contribution/transparency surface. This spec
> ports all of it into the public monorepo, which is canonical from now on.

## Objective

One repository where the social flywheel (claims → votes → settle) and the
honest engine (source_class ladder, recipes, suggest with confidence and
explanation) live together. After L03, the engine lineage is frozen as a
read-only archive and all new work happens here.

## Why a curated port (decision, do not relitigate without new facts)

- **Not cherry-pick:** the histories are unrelated (this repo was born from a
  single squashed commit, engine commits touch private paths that must not
  cross); `git` has no common ancestor to merge through.
- **Not subtree/merge:** migration ids collide — engine `0005_recipe_and_video`
  / `0006_contributor_reported` vs public `0005`–`0010` social tables already
  applied in production. Blind tree inclusion would also drag private
  artifacts (`_bmad-output/`, `规格/`, executor contracts, incident financials).
- **Therefore:** port as fresh curated commits, one per coherent unit, both
  test suites green at every commit. Engine code wins on engine paths; the
  public side's social additions (`--settle-claim`, auth/token plumbing) and
  portability fixes (vendored OpenSSL, VRAM sampling fallback, catalog binding
  flags, warm-start Ollama parse) always survive.

## Dependencies

- U0 (below) is already committed — the public working tree is clean.
- Engine clone available at `~/Work/CanIRunIt` (source of truth for engine
  paths; its 220 py + 54 rs tests define the behavior being ported).
- No production dependency: **L03 lands in git only.** Applying migrations
  0011+ to the `bestmodel-prod` stack is a separate owner-gated deploy step,
  scheduled after the in-flight Story 1.4 collection is uploaded (the
  collection targets the currently deployed contract).

## Stories

### U0 — Clean the public tree (DONE 2026-08-28, Fable)

The rig-session field fixes to `cli/benchmark-probe` (vendored OpenSSL,
`nvidia-smi` VRAM fallback, `--model-release-id`/`--quantization-profile-id`
multipart overrides the API already accepts, optional Ollama load-duration)
were committed together with the missing `UploadRequest` test initializer
update. `cargo test --workspace` green (20 tests).

### U1 — Domain schema + kernel foundation

Port from the engine clone:

- `packages/domain-schema/`: video/recipe additive extensions to
  `schema/benchmark_report.v0.9.0.json`, `src/benchmark_metrics.py`,
  `src/benchmark_report.py`, `src/benchmark_scenario.py`, plus their tests
  (`test_constraints.py`, `test_enums.py`).
- `packages/roofline-kernel/src/estimate_diffusion_step.py` +
  `tests/test_estimate_diffusion_step.py` + the `hardware_fixtures.py` delta.
  Keep the declared `f_attn = 0.05` marked for refit (calibration numbers from
  the 1.4 rig session land in `docs/findings.md` when the cell is uploaded).
- `packages/fake-adapters/src/fake_database.py`: merge engine methods into the
  social FakeDatabase (lockstep rule: same commit as any
  `DatabaseSession` ABC change).

Acceptance: `make test` green; suite count strictly grows by the ported tests.

### U2 — Migrations renumbered + seed union

- `infra/migrations/0011_recipe_and_video.sql` — engine `0005` renumbered.
- `infra/migrations/0012_contributor_reported.sql` — engine `0006` renumbered.
- Append-only rule holds: never touch applied `0001`–`0010`; keep the engine
  files' idempotent style; fix any self-referencing numbering inside the SQL.
- Seed union in `infra/seed/`: engine-only entries (e.g.
  `model-wan22-i2v-flf2v-14b`, the `comfyui` inference runtime) merged into
  the public catalog files, which are otherwise ahead (S22 HF expansion).
- Port `infra/scripts/simulate_video_cells.py` (idempotent uuid5 upsert of
  derived cells).

Acceptance: `make migrate seed` clean on the dev database (port 5434);
`make test` green. Production is explicitly NOT touched by this story.

### U3 — benchmark-probe ComfyUI adapter merge

The only truly bilateral file conflict in the port; do it while it is small.

- Add engine files: `cli/benchmark-probe/src/comfyui_adapter.rs`,
  `cli/benchmark-probe/recipes/` (incl. `wan22-flf2v-720p-81f-v1.json`),
  `tests/comfyui_adapter_smoke.rs`, `tests/comfyui_metrics.rs`,
  `tests/fixtures/`.
- Merge engine deltas into `main.rs`, `execute_benchmark_scenario.rs`,
  `parse_runtime_output.rs`, `lib.rs`, `sign_submission_payload.rs`,
  `upload_benchmark_report.rs`: `--runtime comfyui`, `--scenario`, `--recipe`,
  `--workflow-out`, `--execute` with NDJSON event parsing
  (`parse_comfy_events`) and the 250 ms `nvidia-smi` poller.
- U0's public-side behavior must survive verbatim (settle-claim, binding
  flags, VRAM fallback, vendored OpenSSL).

Acceptance: `cargo test --workspace` green with the union of both suites;
`benchmark-probe --runtime comfyui` dry-run smoke passes against fixtures.

### U4 — Public API engine surface

- New routes + services + schemas from the engine clone:
  `reported_submission_route.py` / `submit_reported_run.py` /
  `reported_submission_schema.py` (POST `/v1/submissions/reported`, per-IP
  quota), `transparency_route.py` / `source_transparency.py`
  (GET `/v1/transparency/sources`), `contributor_route.py` (contribute flow).
- Merge engine deltas into `leaderboard_route.py` / `query_leaderboard.py`
  (`source_class`, `recipe_id`, video scalars) and `submit_benchmark_run.py` /
  `benchmark_submission_schema.py` / `benchmark_submission_route.py`.
- `database_session_provider.py` ABC additions + FakeDatabase lockstep in the
  same commit; register routers in `main.py`.
- Port engine tests (`test_reported_submission_route.py`,
  `test_transparency_route.py`) and merge the leaderboard/submission test
  deltas.

Acceptance: `make test` green; `llms.txt` endpoint inventory updated.

### U5 — `canirunit` crate + harvester package

- New workspace crate `cli/canirunit/` (`confidence.rs`, `transfer.rs`,
  `lib.rs`, `main.rs`) registered in the root `Cargo.toml`; MIT `LICENSE` file
  like the sibling `cli/` members.
- New package `packages/harvester/` (`harvester.py`,
  `model_card_harvester.py`, `comfy_template_harvester.py`,
  `review_queue.py` + tests) wired into the uv workspace; MIT `LICENSE`.
- Harvester principle carries over: structured sources only, never forums;
  everything harvested enters as `harvested` class through the review queue.

Acceptance: `cargo test -p canirunit` green including the property test that
cross-GPU transfer (4090→3090) reproduces the Python estimator within 0.1%;
harvester tests green inside `make test`.

### U6 — Specs, docs, archive freeze

- Import the engine story specs (`story-1.1` … `story-4.4`, Portuguese,
  frozen historical) into `specs/engine-epics/` with a one-paragraph README
  stating provenance and that the implemented code/tests win over prose.
- Port `docs/contribute.md` and `docs/transparency.md`, adapting URLs to this
  repo/API.
- Update `specs/en/AGENTS.md` table (L03 → done) and release notes.
- Tag the engine repo `engine-epics-1-5-final`, add a README pointer to this
  monorepo, and stop committing there (owner pushes the tag).

Acceptance: `make gate` full e2e PASS on the unified repo.

## Global invariants (all stories)

1. One commit per story, conventional message `feat(U3): ...`, owner git
   identity (`-c user.name="Carlos Felipe" -c user.email="dev@local"`).
2. `make test` and `cargo test --workspace` green at every commit; the ported
   engine tests must all be present and green by U6 (no silent drops).
3. Nothing crosses from the engine clone except code, tests, seeds, specs and
   the two public docs. Never: `_bmad-output/`, `规格/`, executor contracts
   (`CONTRATO-GLOBAL.md`, `ESTADO.md`, `PROMPT-EXECUTOR.md`), incident
   financials, ops handoffs.
4. Licensing follows the repo split: MIT for `packages/**` and `cli/**`
   additions (add LICENSE files), AGPL-3.0 for `apps/**` changes.
5. Migrations append-only from 0011; production untouched until the owner
   schedules the deploy (after the 1.4 cell is uploaded).
