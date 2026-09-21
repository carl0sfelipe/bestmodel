# S37 — CLI ergonomics baseline (clap migration)

> Decision source: `specs/en/L05-cli-maturation.md` D1/D2/D9. Migrates both CLI
> crates to `clap` so the product behaves like a normal CLI (`--version`,
> uniform help/errors, documented exit codes) and gives the new subcommands
> (S39/S40/S41/S42) a real subcommand tree instead of more special-casing
> before the legacy parser. Keystone of the cluster.

## Objective

`benchmark-probe` and `canirunit` parse arguments with `clap` (derive), keeping
every existing flag and the `lab` behavior byte-for-byte, and gain `--version`,
consistent `--help`, uniform error style, documented exit codes, a "SEE ALSO"
cross-pointer between the two binaries, and (optional) shell completion.

## Scope

In: replace the manual parsers in `cli/benchmark-probe/src/main.rs` and
`cli/canirunit/src/main.rs` with `clap`; wire `--version`/`-V` from the existing
`CARGO_PKG_VERSION`; preserve all current flags, defaults, ENV vars and the
`lab` subcommand; add a documented exit-code table; add "SEE ALSO".
Out: any new subcommand (S39–S42); merging the two binaries (D2 rejection);
universal `--dry-run` (D9 rejection); changing any flag's meaning or default.

## Contract

1. `cli/benchmark-probe/Cargo.toml` and `cli/canirunit/Cargo.toml` gain a
   `clap` dependency (derive feature). Optional: `clap_complete` for
   completion, only if it does not delay the story.
2. `benchmark-probe`: a clap command tree whose default (no subcommand) path
   keeps the current measurement flags (`--runtime`, `--model`, `--output`,
   `--sign`, `--upload`, `--settle-claim`, `--print-command`, `--artifact`,
   `--report-runtime`, and the rest already parsed today) with identical
   semantics, and whose `lab` subcommand keeps its current flags. `--version`
   prints `benchmark-probe <semver>`.
3. `canirunit`: clap tree over the existing `rigs` and `suggest` subcommands
   with identical flags; `--version` prints `canirunit <semver>`.
4. Exit codes documented in each `--help` epilog and in
   `cli/benchmark-probe/AGENTS.md`: `0` success, `2` usage error, and the
   existing runtime error codes preserved (do not renumber current non-zero
   exits).
5. Each `--help` includes a "SEE ALSO" line naming the sibling binary
   (`benchmark-probe` ↔ `canirunit`).

## Rules

Do not invent a flag, subcommand, ENV var, or exit code beyond those already
parsed today — every preserved item was read from `cli/*/src/main.rs`. Do not
fake a capability: a path that is not yet implemented must not print a success
banner (Rust analogue of "never use `declare const` as a workaround" — do not
stub a flag into existence). Never weaken an existing test to make clap pass;
`tests/cli_smoke.rs` and `tests/test_tuning_search.rs` stay green unchanged.

## Verified data (2026-09-21)

- `benchmark-probe --version` → "unknown argument", exit 2; `VERSION =
  env!("CARGO_PKG_VERSION")` already exists in `main.rs`.
- Neither `Cargo.toml` lists `clap`/`structopt` (manual parsing).
- `lab` is dispatched before the legacy parser (`main.rs` line ~53);
  `cli_smoke.rs` drives the real binary end-to-end.
- Two binaries present: `benchmark-probe`, `canirunit`.

## Acceptance (each criterion = one command)

1. Build stays green: `cargo build --release -p benchmark-probe -p canirunit`
2. `--version` now works (was exit 2): `./target/release/benchmark-probe --version | grep -Eq '^benchmark-probe [0-9]+\.[0-9]+\.[0-9]+'`
3. `-V` short flag: `./target/release/benchmark-probe -V | grep -Eq '[0-9]+\.[0-9]+\.[0-9]+'`
4. canirunit versioned too: `./target/release/canirunit --version | grep -Eq '^canirunit [0-9]'`
5. `lab` preserved: `./target/release/benchmark-probe lab --help >/dev/null`
6. Legacy behavior preserved (real binary smoke): `cargo test -p benchmark-probe -q`
7. clap is the parser: `grep -q '^clap' cli/benchmark-probe/Cargo.toml && grep -q '^clap' cli/canirunit/Cargo.toml`
8. Exit codes documented: `grep -qi 'exit code' cli/benchmark-probe/AGENTS.md`

## Oráculo

- comando: cargo build --release -p benchmark-probe -p canirunit && ./target/release/benchmark-probe --version | grep -Eq '^benchmark-probe [0-9]+\.[0-9]+\.[0-9]+' && ./target/release/canirunit --version | grep -Eq '^canirunit [0-9]' && ./target/release/benchmark-probe lab --help >/dev/null && cargo test -p benchmark-probe -q
- exit esperado: 0 — clap parses both binaries, `--version`/`-V` print
  name+semver, `lab` and all legacy flags still work, smoke tests green. Before
  the migration the same command fails at `--version` (exit 2) — the clean red
  state, not a broken oracle.

## Dependencies / out of scope

- Depends on: nothing (keystone).
- Out: new subcommands (S39–S42), binary merge (D2), completion if it risks the
  story, crates.io publish (D4/A11).
