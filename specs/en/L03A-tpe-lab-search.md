# L03A — TPE lab search over llama.cpp serving flags (stub-objective proof)

> Slice of L01/L03 (`specs/en/L01-cli-v2-local-lab.md`), pulled ahead of the
> L02 HTTP sweep runner so the intelligent search is proven rig-independent.
> Owner decision 2026-08-30: the optimizer is **argos-opt** (`~/Work/argos-opt`,
> dual MIT/Apache-2.0) — this answers open question 1 of the L01 cluster
> ("embedded TPE vs argmin BO": neither; our own no-deps TPE crate).
> The first real objective is llama.cpp serving flags on the 3090 — searched
> by TPE, NEVER by brute force/grid as the primary strategy (grid/random
> exist only as measurement baselines).

## Objective

Não invente número, prazo ou fonte além dos listados em Verified data —
every number below is either measured, pinned by argos-opt's spec, or
marked [A DEFINIR] until measured.

`benchmark-probe lab --stub --trials N` runs an intelligent search over the
llama.cpp serving-flag space using argos-opt's TPE, records every trial to a
resumable lab directory (L01 recorder format), and prints the best config as
a ready-to-paste `llama-server` command. The same binary, with the stub
swapped for the real bench script (owner's "sobe" on the 3090), is the L02
integration — the loop does not change.

## Verified data

- argos-opt API consumed (verificado 2026-08-30, main 31feea6): `Space::new`,
  `Dim::{Continuous, Integer, Categorical}`, `Optimizer::new/resume`,
  `run(max_evals, f) -> usize`, `best()`, `TrialLog::save/load`,
  `TrialResult::{Value, Failed}`; deps of argos-opt: serde/serde_json only.
- Path dependency until the crate is published (name pending):
  `argos-opt = { path = "../../../argos-opt" }` (verificado: resolves to
  ~/Work/argos-opt from cli/benchmark-probe).
- llama.cpp flag surface (llama-optimus pattern, L01 spec): `-ngl`, `-c`
  (ctx), `-t` (threads), KV cache type (`--cache-type-k/-v`), `-fa`
  (flash-attention).
- Stub measurement is a SIMULATION and must say so in every output line —
  fake tok/s never travels to any server, report or claim.

## Frozen contract

```rust
// tuning_search.rs
pub struct LabSpace;                       // the llama.cpp serving space
LabSpace::new() -> Result<LabSpace, String>
LabSpace::space(&self) -> &argos_opt::Space
LabSpace::to_server_command(&self, params: &[Value], model: &str) -> String
// dims (FROZEN order):
//   0 ngl        Integer   0..=999
//   1 ctx        Integer   512..=32768
//   2 threads    Integer   1..=32
//   3 kv_cache   Categorical ["f16","q8_0","q4_0"]
//   4 flash_attn Categorical ["off","on"]

pub fn run_lab(
    max_evals: usize, seed: u64,
    objective: &mut impl FnMut(&Vec<Value>) -> Result<f64, ()>,
    out_dir: &Path,               // experiments/<label>/: meta.json + index.jsonl + best.json
) -> Result<LabOutcome, String>    // LabOutcome { best_params, best_value, trials }

pub fn stub_objective(params: &[Value]) -> Result<f64, ()> {
    // DETERMINISTIC simulation, documented as fake:
    // VRAM budget 24 GiB: weights 16 GiB * ngl/999 + ctx * kv_bytes(kv_cache)
    //   over budget -> Err(()) (the OOM path; Failed trial)
    // tok/s = shaped interior optimum over all 5 dims + seeded noise < 2%
    // deterministic: same params -> same tok/s, always
}

// lab_recorder.rs
LabRecorder::create(dir, meta: LabMeta) / .append(trial_idx, params, value) / .finish(best)
// index.jsonl: one JSON line per trial {"trial":n,"params":[...],"value":x|null}
// meta.json: {"method":"tpe","seed":n,"max_evals":n,"space":[dims],"objective":"stub|command"}
// best.json: {"params":[...],"value":x,"server_command":"llama-server ..."}
```

CLI (new, first subcommand; legacy flag parsing untouched — first arg is
dispatched only when it is exactly `lab`):

```
benchmark-probe lab --stub [--trials 60] [--seed 42] [--out experiments/] [--json]
```

Behavior: exit 0 prints the best server command + tok/s + trial count;
`--json` prints the best.json content; every stdout line containing tok/s
says `SIM`. Failed trials (OOM in the stub) appear in index.jsonl as
`"value": null` and never win `best`.

## Mandatory behaviors (each with a test)

1. **Determinism**: same `--seed`, same best config and same index.jsonl
   across two runs.
2. **OOM path**: a params set over the stub's VRAM budget returns
   `Err(())`; through `run_lab` it lands in index.jsonl as null and is
   excluded from `best`.
3. **Intelligent beats brute (the owner's constraint, measured)**: on the
   stub, TPE with seed 42 at 60 trials reaches a best tok/s strictly
   above the uniform-random baseline's best at the same budget and seed.
   The quality bar pinned in the test is the MEASURED midpoint between
   the two at freeze time, with the measured values recorded here —
   never tuned to let a cut pass.
4. **No repeats**: across a full `run_lab`, no evaluated params vector
    repeats (argos-opt never re-answers a known question). AJUSTE
    registrado 2026-08-30, pré-verde: a afirmação original de que o
    baseline aleatório "DOES repeat" foi retirada — em espaço 5D misto
    com inteiros de amplitude 32k, duplicata exata de vetor completo é
    evento raro; exigir duplicata no random seria exigir ruído.
5. **Recorder**: interrupted run (simulate: create recorder, append 10,
   drop) → file exists, 10 lines, valid JSONL; `--out` directory is
   created fresh per label `<UTC-timestamp>-stub`.
6. **Server command**: `to_server_command` renders the 5 dims into the
   llama-server invocation (`-ngl`, `-c`, `-t`, `--cache-type-k/v`,
   `-fa`) in frozen order, model placeholder `MODEL.gguf`.
7. **CLI smoke**: the real binary with `lab --stub --trials 20` exits 0,
   writes meta/index/best, prints a `SIM` line; legacy single-run flags
   still parse (no regression in existing smoke tests).

## Out of scope (do not invent features beyond these)

- No HTTP to llama-server/Ollama (L02), no priors endpoints (L04), no
  report/contribute commands (L05/L06), no Ollama tuner (L07).
- No new dependency besides argos-opt (path) — benchmark-probe dep list
  otherwise frozen.
- Do not invent tok/s numbers outside `stub_objective`'s formula; the
  real 3090 numbers only exist after the owner's "sobe" + real bench.
- NUNCA declare that the stub measures anything real — every SIM-marked
  line is fake by construction.

## Verificação

VERIFICACAO: grep -q "tuning_search" src/lib.rs && grep -q "argos-opt" Cargo.toml && grep -q "run_lab" src/tuning_search.rs

## Barra

Raise the test-3 quality bar when the engine improves; lower nothing.

## Oráculo

- comando: cargo test -p benchmark-probe --quiet && cargo run -p benchmark-probe --quiet -- lab --stub --trials 20 --json
- exit esperado: 0 — full suite green AND the stub lab run completing
  with a best config, SIM-marked output, and the three files on disk.
  Before implementation this fails (no lab subcommand) — red by design.
