# AGENTS.md — rawpack

Read order: this file → the one spec you were dispatched (`specs/R0x-*.md`) →
`stages/CONTRACT.md` if you touch a stage → `shared/pack-schema/src/main/resources/rawpack/pack.schema.json`
if you touch the pack. Do not read the other specs.

Rules:

- The JSON Schema is the only definition of a pack. Kotlin models, Python stages,
  Bend2 stages validate against it; a shape restated by hand is a bug.
- A stage never writes into `--in`, never reaches the network at run time, always
  writes `result.json` (see contract). `dry_run` exists so CI can prove the contract
  without a GPU.
- Numbers are measured (`bench/results/`) or absent. `[A DEFINIR]` is a valid value;
  a plausible default is not.
- One story = one file = one oracle. The oracle must fail for the right reason before
  the work exists (`test -x ./gradlew && …`), never with `command not found`.
- Commit messages in English; incident diary entries in Portuguese (llms.surf format).
- `.dispatch/` is the dispatcher's; never commit it.
