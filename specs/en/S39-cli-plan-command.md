# S39 — `plan` command (catalog SOTA + predictors)

> Decision source: `specs/en/L05-cli-maturation.md` D5, realizing backlog A9.
> `plan` is the loop's entry — "what is the best SOTA I can run here, and how?" —
> and it is exactly what the site `/cli` (L04 S33) quarantines today. It ranks
> from the **catalog** plus roofline predictors, not only the local measured
> corpus (the A9 gap `canirunit suggest` cannot cover).

## Objective

`benchmark-probe plan` prints ranked model candidates for a target GPU from the
catalog (SOTA models) scored by the roofline predictors, offline-capable
(predictors-only fallback), with `--json` for agents. Every row declares its
basis; no number is presented as measured unless it is.

## Scope

In: a `plan` subcommand reading the in-repo catalog + pool snapshot + roofline
kernel; `--gpu <rig-id>` (like `suggest`), offline predictors-only fallback,
`--json`; honest basis labels (measured/reported/extrapolated/formula/no data).
Out: online priors endpoint (`/v1/priors/hardware-similar` is L01 backend, out
of this cut); any engine run; auto-download of models (A2 real-lab, out).

## Contract

1. `cli/benchmark-probe/src/plan_candidates.rs` (new) + a `plan` subcommand in
   the clap tree (S37): given `--gpu <rig-id>` (or detected topology), join the
   catalog model list against the roofline VRAM/throughput predictors and the
   pool snapshot; emit a ranked list `model × quant × predicted throughput ×
   basis`.
2. Offline fallback: with no network and no pool cell, rank by predictors only,
   labelled `formula`/`extrapolated` — never `measured`.
3. `--json` emits a stable object `{ gpu, task, candidates: [ { model_release_id,
   quant, expected, basis, source_class, explanation } ] }`; human output is a
   plain-text table.
4. A missing GPU prints the closest known rig ids (like `suggest`) and exits
   non-zero — never a guessed number.

## Rules

Never invent a tok/s or fill an empty cell; a candidate without a source class
does not render (honesty ladder). Do not document or dispatch a flag the
command does not implement in the same commit (anti-phantom; no stubbed success
— the Rust analogue of "never use `declare const` as a workaround"). Reuse the
roofline kernel and catalog already in the repo — do not hardcode a model list.
Do not weaken existing predictor tests.

## Verified data (2026-09-21)

- A9: `canirunit suggest` ranks the lab corpus but never proposes catalog SOTA
  (Qwen3.6-35B-A3B etc.); `plan` is the missing command (backlog Track A).
- The roofline predictors live in `packages/roofline-kernel`; the pool snapshot
  is `apps/web/data/derived/pool.json`; catalog/GPU specs are in-repo
  (`cli/canirunit/gpu_transfer_specs.json`, seed catalog).
- A6 (MoE residency) is OPEN — MoE predictions may under-predict; they are
  labelled by basis, never shown as measured.

## Acceptance (each criterion = one command)

1. Subcommand exists (was clap usage error): `./target/release/benchmark-probe plan --gpu rtx-3090-24gb --json >/dev/null`
2. Output is valid JSON with candidates: `./target/release/benchmark-probe plan --gpu rtx-3090-24gb --json | python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["candidates"],"empty";assert all("source_class" in c for c in d["candidates"])'`
3. Every candidate declares a basis (no un-classed number): `./target/release/benchmark-probe plan --gpu rtx-3090-24gb --json | grep -q 'source_class'`
4. Unknown GPU is honest (non-zero, suggests neighbours): `./target/release/benchmark-probe plan --gpu no-such-gpu; test $? -ne 0`
5. Offline path still ranks (predictors only): `BENCHMARK_PROBE_API_URL=http://127.0.0.1:1 ./target/release/benchmark-probe plan --gpu rtx-3090-24gb --json | python3 -c 'import sys,json;assert json.load(sys.stdin)["candidates"]'`

## Oráculo

- comando: cargo build --release -p benchmark-probe && ./target/release/benchmark-probe plan --gpu rtx-3090-24gb --json | python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["candidates"];assert all("source_class" in c for c in d["candidates"])'
- exit esperado: 0 — `plan` ranks catalog candidates for the GPU with a basis
  on every row, offline-capable. Before the command exists the same invocation
  fails at clap parsing (usage error, non-zero) — the clean red state.

## Dependencies / out of scope

- Depends on: S37 (subcommand tree).
- Out: `/v1/priors/hardware-similar` (L01 backend), engine runs, A5/A6
  recalibration (surfaced by basis, not gated here).
- Coupling: L04 S33 `/cli` may un-quarantine `plan` in the commit this ships.
