# S40 — `report` command (measured-vs-predicted)

> Decision source: `specs/en/L05-cli-maturation.md` D6. `lab` already writes
> `experiments/<label>/{meta.json,index.jsonl,best.json}`; `report` is the
> reader that turns that data into a config/measured/predicted/delta table and a
> copy-paste best command line. It needs no engine run and no A5 (it displays
> the delta, it does not gate on it).

## Objective

`benchmark-probe report [--label <name>]` reads an existing lab directory and
prints `config | measured | predicted | delta` with the best configuration and
its ready-to-paste serving command; `--json` and `--markdown` for machine and
doc consumption.

## Scope

In: a `report` subcommand over `experiments/<label>/` (default: latest);
measured-vs-predicted delta via the roofline kernel; best config + command
line; `--json`/`--markdown`.
Out: running the lab (that is `lab`); uploading (that is `contribute`, S41);
the 0.9.1 statistics/tuning contract blocks (deferred backend line).

## Contract

1. `cli/benchmark-probe/src/report_lab.rs` (new) + a `report` subcommand in the
   clap tree (S37): load `index.jsonl`/`best.json` from
   `experiments/<label>/` (default = most recent immutable dir), join measured
   cells against the roofline prediction, and render the delta table.
2. Best config line: emit the exact `llama-server` / Ollama command for the
   winning cell (the flags already recorded in the lab dir), copy-paste ready.
3. `--json` emits a stable object; `--markdown` emits a table document; default
   is plain text. A missing/empty lab dir exits non-zero with a clear message
   (no fabricated rows).

## Rules

Never invent a measured or predicted number — both come from the lab dir and
the roofline kernel; SIM/stub cells stay labelled SIM (never presented as a
real benchmark). Do not document a flag not implemented in the same commit
(anti-phantom; no stubbed success). The Rust analogue of "never use
`declare const` as a workaround": do not stub a flag into fake success. Do not
mutate the immutable lab dirs. Do not weaken existing lab-recorder or predictor
tests.

## Verified data (2026-09-21)

- `lab_recorder.rs` writes `experiments/<label>/{meta.json,index.jsonl,
  best.json}`, append-only, one JSON line per trial, dirs immutable once
  created (`cli/benchmark-probe/AGENTS.md`).
- `benchmark-probe lab --stub --trials N` produces such a dir today
  (SIM-marked).
- The roofline kernel (`packages/roofline-kernel`) provides the predicted side.

## Acceptance (each criterion = one command)

Set up a lab dir first: `./target/release/benchmark-probe lab --stub --trials 5`.

1. Subcommand exists (was clap usage error): `./target/release/benchmark-probe report --json >/dev/null`
2. Report is valid JSON with rows and a best config: `./target/release/benchmark-probe report --json | python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["rows"];assert d["best"]'`
3. Delta column present: `./target/release/benchmark-probe report --json | grep -q 'delta'`
4. Markdown renders a table: `./target/release/benchmark-probe report --markdown | grep -q '|'`
5. Empty/missing lab dir is honest (non-zero): `./target/release/benchmark-probe report --label does-not-exist; test $? -ne 0`

## Oráculo

- comando: cargo build --release -p benchmark-probe && ./target/release/benchmark-probe lab --stub --trials 5 && ./target/release/benchmark-probe report --json | python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["rows"];assert d["best"];assert any("delta" in r for r in d["rows"])'
- exit esperado: 0 — `report` reads the lab dir and prints measured-vs-predicted
  rows with a best config. Before the command exists the same invocation fails
  at clap parsing (usage error, non-zero) — the clean red state.

## Dependencies / out of scope

- Depends on: S37 (subcommand tree). Reads output that `lab` already produces.
- Out: `contribute` (S41), 0.9.1 statistics blocks, engine runs.
