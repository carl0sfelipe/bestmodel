# S25: Parity & modality-blind gate (post-escalation hardening)

Implements `docs/direction-2026-08-29.md` D3 (fake↔real parity), D5 (video leg
in the gate) and the S25d co-location slice of D4 (per-folder AGENTS.md
checklists). Scope guard: S23/S24/L01/cloud are NOT in this story; S26 (contract
0.9.1) is the follow-up that reshapes the schema itself — S25 changes no
migration.

## Dados verificados (verified on-disk facts — the only inputs allowed)

Checked on branch `s25` (tree identical to `main` @ 282f9f1), 2026-08-30:

- `make test` = `uv run pytest -q`; baseline 300 passed in ~6 s.
- `make gate` = `bash infra/scripts/e2e_gate.sh`; today it uploads one LLM mock
  run only (no video anywhere in the gate).
- `DatabaseSession` ABC: `apps/public-api/src/dependencies/database_session_provider.py:20`
  (~74 abstract methods). `PostgresSession` at `:332`. `FakeDatabase`:
  `packages/fake-adapters/src/fake_database.py:33` (imports the ABC via
  `from src.dependencies.database_session_provider import DatabaseSession`).
- `insert_benchmark_run` writes exactly 16 columns (`provider.py:519`):
  id, hardware_submission_id, model_release_id, quantization_profile_id,
  inference_runtime_id, benchmark_scenario_id, status, client_version,
  signature, payload_digest, recipe_id, source_class, seconds_per_clip,
  it_per_s, frames_per_s, source_url. `insert_scenario` writes 15
  (`provider.py:507`): id, scenario_kind, prompt_tokens, generated_tokens,
  context_tokens, batch_size, tensor_parallel, width, height, frames, steps,
  cfg, shift, seed — minus `id`/`scenario_kind`/`tensor_parallel` all are
  nullable for video rows (migration 0011).
- No session-API method returns a run/scenario row by id (`find_run_by_lookup`
  returns `{"id"}` only; `fetch_validated_runs` returns a partial column list
  without video scalars).
- `fetch_leaderboard_entries` (`provider.py:432`) already projects
  `run.recipe_id, run.source_class, run.seconds_per_clip, run.it_per_s,
  run.frames_per_s`; `query_leaderboard` drops entries without `source_class`.
- FakeDatabase divergences found: `fetch_leaderboard_entries` returns a
  hand-populated list (`add_leaderboard_entry`) instead of deriving from
  inserted runs; the recipe catalog row is hand-duplicated from migration
  0011's INSERT; `insert_*` accept records with missing/extra keys that
  Postgres would reject (missing key → psycopg error; extra key → silently
  ignored).
- Worker: video evidence keys `extract_runtime_evidence.py:13`
  (`seconds_per_clip, it_per_s, frames_per_s, peak_vram_mib`), tolerance 0.10;
  video duration check = frames / frames_per_s
  (`validate_submission_payload.py:_duration_plausible`); hydration reads the
  video scalars from the run row (`postgres_repository.py:fetch_run_payload`).
- CLI video evidence format (main.rs `build_video_evidence`): one
  `metric <key> <value>` line per line, keys above.
- Seeds: `model-wan22-i2v-flf2v-14b` in `infra/seed/model_releases.json`,
  `comfyui` runtime and `q-fp16` quant in their seed JSONs; recipe seeded by
  migration 0011.
- `hardware_submission.owner_account_id` is UUID NOT NULL with NO FK
  (migration 0001) — community owner id needs no app_user row.
- Feasibility filter passes rows with `peak_vram_mib` NULL or 0
  (`filter_feasible_models.py`) — video rows are not silently hidden.
- The signed-submission endpoint has no per-IP quota (that is the reported-run
  endpoint only); `challenge_nonce` is required by `SubmissionForm`.
- 5 of the 6 S25d target folders already have an AGENTS.md; none has a
  "Change checklist" section; `infra/migrations/AGENTS.md` does not exist.

Nao invente numero, campo, comando, nome de arquivo ou comportamento alem dos
listados acima; campo nao decidido vira [A DEFINIR], nunca em branco.
NUNCA use declare const (ou qualquer stub de compilacao) como workaround — importe e execute o codigo real.

## Sub-stories

### S25a — single source of the run shape + ABC inventory

1. New module `packages/domain-schema/src/run_record.py`: pydantic v2 models
   `BenchmarkRunRecord` (exactly the 16 insert columns; the 10 NOT NULL-ish
   service-required keys required, the 6 nullable keys required-but-Optional,
   i.e. no defaults — a missing key is a contract error) and
   `BenchmarkScenarioRecord` (15 columns; `id`, `scenario_kind`,
   `tensor_parallel` required, the rest required-but-Optional). Both with
   `model_config = ConfigDict(extra="forbid")` — typos and stray keys fail.
   Owner principle (D2 direction): few hard-required fields, everything
   modality-specific opt-in/nullable; no enums here.
2. `FakeDatabase.insert_scenario` / `insert_benchmark_run` validate the record
   through these models before storing (the fake now rejects what Postgres
   rejects). FakeDatabase keeps its canned leaderboard behavior — deriving it
   is a behavior change beyond S25 scope (see Divergences note below).
3. New ABC methods `find_run_by_id(run_id)` and `find_scenario_by_id(scenario_id)`
   returning the full row dict or None; implemented in PostgresSession
   (`SELECT *`) and FakeDatabase. Every existing caller is untouched.
4. Test `tests/test_session_contract.py` (runs in `make test`): introspects
   `DatabaseSession.__abstractmethods__` and fails naming any method missing
   from FakeDatabase or PostgresSession; instantiates `PostgresSession(None)`
   as a registered-subclass smoke.

### S25a-rt — video round-trip in BOTH backends

Test `tests/test_session_video_roundtrip.py`: one parametrized scenario —
write a video scenario row + a video benchmark_run row through the session API
(unique uuids, seed-catalog FK ids, video scalars with binary-exact float
values), read both back via `find_scenario_by_id`/`find_run_by_id`, assert:

- record field-set equality generated from `BenchmarkRunRecord.model_fields` /
  `BenchmarkScenarioRecord.model_fields` (never a hand-maintained list);
- `source_class`, `recipe_id`, `seconds_per_clip`, `it_per_s`, `frames_per_s`
  round-trip with the written values;
- scenario video fields (`width/height/frames/steps/cfg/shift/seed`) round-trip.

Backends: FakeDatabase always (in `make test`); PostgresSession when
`DATABASE_URL` is set and reachable — otherwise the test SKIPS with an explicit
reason (never silently passes). The Postgres leg wraps one psycopg connection
in `PostgresSession`, rolls back on teardown (no rows left behind).

### S25b — video leg in the gate

`infra/scripts/e2e_gate.sh` gains, after the existing LLM upload section:

1. Build a mock-ComfyUI video report fixture (python heredoc; no ComfyUI
   execution): `runtime: comfyui`, `runtime_version: 0.3.48`, VideoScenario
   (1280x720, 81 frames, 20 steps, cfg 3.5, shift 5.0, seed 42),
   `recipe_id: wan22-flf2v-720p-81f-v1`, LLM metrics 0, video scalars
   consistent (frames / seconds_per_clip), a per-run random hardware
   fingerprint (dedupe never trips on gate re-runs); artifact_0 = fixture
   NDJSON with the 4 `metric <key> <value>` lines at the exact written values;
   signed with the gate key (canonical JSON sha256 + Ed25519, same as the
   service verifies).
2. POST it to `/v1/submissions` (nonce + form fields incl. `recipe_id`,
   `inference_runtime_id=comfyui`, `model_release_id=model-wan22-i2v-flf2v-14b`,
   `quantization_profile_id=q-fp16`); gate log shows the POST and asserts 202.
3. Assertions, all printed as PASS/FAIL lines: (a) the run reaches
   `status='validated'` in Postgres (poll with timeout, like the LLM leg);
   (b) validated-run count before < after (leaderboard row count increased)
   and the `/v1/leaderboard` entry for the run carries a non-empty
   `source_class`; (c) the leaderboard entry carries the written
   `seconds_per_clip`/`frames_per_s` (video scalars round-trip end to end).
4. Run the S25a-rt Postgres leg inside the gate (`DATABASE_URL` already
   exported there): `uv run pytest tests/test_session_video_roundtrip.py -q`.

### S25d — AGENTS.md change checklists (co-location)

Add a "## Change checklist" section (what to check when touching this package,
pointing at the lockstep rule: run-shape change ⇒ update the single source +
both backends + round-trip before commit) to the AGENTS.md of each:
`packages/domain-schema`, `packages/fake-adapters`, `apps/public-api`,
`apps/intake-worker`, `cli/benchmark-probe` (sections added to the existing
files, content preserved) and create `infra/migrations/AGENTS.md` (map +
checklist + append-only rule carried from `infra/AGENTS.md`).

## Divergences & decisions (prompt vs disk)

- The mission prompt's S25a sketch says "FakeDatabase DERIVA dele (ou valida
  contra ele)" — disk shows the fake's leaderboard is canned; full derivation
  is a behavior change touching every leaderboard test. Decision: implement
  the sanctioned "valida contra ele" arm for writes (S25a.2) and leave
  leaderboard derivation to S26, recorded here deliberately.
- D4 also prescribes LOAD-BEARING comments and a gate grep for AGENTS.md
  presence; the mission prompt scopes S25d to the checklists only. Decision:
  prompt scope wins; the two extras are [A DEFINIR] follow-ups.

## Verificação

VERIFICACAO: grep -c "Change checklist" packages/domain-schema/AGENTS.md packages/fake-adapters/AGENTS.md apps/public-api/AGENTS.md apps/intake-worker/AGENTS.md cli/benchmark-probe/AGENTS.md infra/migrations/AGENTS.md

## Oráculo

Cada sub-story fecha com seu comando; exit 0 (ou a saida declarada) e a prova.

- comando: uv run pytest tests/test_session_contract.py tests/test_session_video_roundtrip.py -q
- comando: DATABASE_URL=postgresql://bestmodel:bestmodel@localhost:5434/bestmodel uv run pytest tests/test_session_video_roundtrip.py -q
- comando: bash infra/scripts/e2e_gate.sh
- comando: grep -L "Change checklist" packages/domain-schema/AGENTS.md packages/fake-adapters/AGENTS.md apps/public-api/AGENTS.md apps/intake-worker/AGENTS.md cli/benchmark-probe/AGENTS.md infra/migrations/AGENTS.md

Esperado: o primeiro comando passa com a perna fake (postgres leg SKIP se sem
DATABASE_URL); o segundo passa com a perna postgres (saida "passed" com skip
zero para a perna); o terceiro termina "GATE RESULT: PASS" e o log contem as
linhas "POST /v1/submissions (video mock)" e "source_class"; o quarto comando
nao imprime NENHUM arquivo (todos os 6 tem a secao).
