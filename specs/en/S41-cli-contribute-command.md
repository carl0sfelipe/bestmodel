# S41 — `contribute` command (existing contract 0.9.0)

> Decision source: `specs/en/L05-cli-maturation.md` D7, with consent per backlog
> A3 (owner-decided: opt-out transparent). Closes the flywheel: the best
> validated lab cell(s) become **existing** contract-0.9.0 signed reports and
> upload through the **existing** intake. CLI-only — no backend change. The
> 0.9.1 statistics/tuning contract evolution is a separate deferred line.

## Objective

`benchmark-probe contribute` converts the best cell(s) of a lab session into
signed contract-0.9.0 reports and uploads them via the existing intake, with an
opt-out **transparent** consent (A3) and an always-honored `--no-upload`.

## Scope

In: a `contribute` subcommand reading `experiments/<label>/`; convert best
cell(s) → existing signed report(s) (reuse the current sign path); upload via
the existing nonce + multipart intake; A3 consent (visible, pre-checked,
one-click opt-out); `--no-upload` local-only.
Out: contract 0.9.1 blocks (statistics/tuning/spec_decode) and the matching
worker anti-fraud — deferred backend line; per-user attribution wiring is S42
(this story consumes it if present, works with the global key if not);
validation acceptance (gated by A5).

## Contract

1. `cli/benchmark-probe/src/contribute_lab.rs` (new) + a `contribute`
   subcommand in the clap tree (S37): select the best cell(s) from
   `best.json`/`index.jsonl`, build a contract-0.9.0 report per cell using the
   **existing** `sign_submission_payload` path, and upload via the **existing**
   `upload_benchmark_report` (nonce + multipart).
2. Consent (A3): first run shows a visible, pre-checked opt-in notice framing
   "sharing improves predictions for everyone"; unchecking (or `--no-upload`)
   is one step and always honored; the choice is stored in the config file
   (S42). SIM/stub cells are never uploaded (they are not measured).
3. If a per-user signing key is registered (S42), reports carry
   `signature_key_id`; otherwise the legacy global-key path is used unchanged.
4. `--no-upload` writes the signed report bundle locally and performs no network
   call.

## Rules

Never upload a SIM/stub cell or present it as measured; never fabricate a
"validated" status — the CLI reports what the server returns (accepted/
quarantined), it does not decide validation (anti-phantom; no stubbed success,
the Rust analogue of "never use `declare const` as a workaround"). Never invent
a metric or a contract field beyond 0.9.0. Consent defaults are exactly A3
(opt-out transparent) — do not silently upload and do not hide the notice. Do
not weaken the existing sign/canonical-JSON/digest tests.

## Verified data (2026-09-21)

- `sign_submission_payload.rs` builds the report, canonical JSON, SHA-256
  digest and Ed25519 signature (SCHEMA_VERSION 0.9.0); `upload_benchmark_report.rs`
  does nonce + multipart — both exist and are test-pinned.
- `lab` writes `experiments/<label>/best.json` today (SIM-marked stub cells).
- A3 is owner-decided (opt-out transparent + llms.surf giveaway gamification).
- A5 (roofline threshold) OPEN → contributed lab runs may quarantine; that is a
  server-side validation outcome, not this command's success condition.

## Acceptance (each criterion = one command; offline `--no-upload` path)

Set up a lab dir first: `./target/release/benchmark-probe lab --stub --trials 5`.

1. Subcommand exists (was clap usage error): `./target/release/benchmark-probe contribute --no-upload --output-dir /tmp/bm-contrib >/dev/null`
2. It produces a signed report bundle: `ls /tmp/bm-contrib/*.json && ls /tmp/bm-contrib/*.signature`
3. The report is contract 0.9.0: `python3 -c 'import json,glob;d=json.load(open(sorted(glob.glob("/tmp/bm-contrib/*.json"))[0]));assert d["schema_version"].startswith("0.9")'`
4. `--no-upload` makes no network call (runs with API pointed at a dead port): `BENCHMARK_PROBE_API_URL=http://127.0.0.1:1 ./target/release/benchmark-probe contribute --no-upload --output-dir /tmp/bm-contrib2 && ls /tmp/bm-contrib2/*.json`
5. Consent notice is visible on the upload path: `./target/release/benchmark-probe contribute --help | grep -qi 'no-upload'`

## Oráculo

- comando: cargo build --release -p benchmark-probe && ./target/release/benchmark-probe lab --stub --trials 5 && ./target/release/benchmark-probe contribute --no-upload --output-dir /tmp/bm-contrib && python3 -c 'import json,glob;f=sorted(glob.glob("/tmp/bm-contrib/*.json"));assert f;d=json.load(open(f[0]));assert d["schema_version"].startswith("0.9")' && ls /tmp/bm-contrib/*.signature
- exit esperado: 0 — `contribute --no-upload` turns the best lab cell into a
  signed contract-0.9.0 report bundle on disk. Before the command exists the
  same invocation fails at clap parsing (usage error, non-zero) — the clean red
  state. The live-upload leg (202 accepted) is an integration check against a
  running API and is not part of this offline oracle.

## Dependencies / out of scope

- Depends on: S37 (subcommand tree) and S42 (per-user attribution; degrades to
  the global key if absent). Consumes `lab`'s output.
- Out: contract 0.9.1 + worker anti-fraud (deferred line); validation
  acceptance (A5); the giveaway ranking (llms.surf side).
