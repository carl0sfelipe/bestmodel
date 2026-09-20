# Stage contract v1

Every processing step of rawpack — fusion, development, editing, scoring — is a
**stage**: an executable that reads a pack directory and writes an output
directory plus `result.json`. The orchestrator (Kotlin) and `bench/` know only
this contract; a stage may be Python + CUDA, a Rust/vkdt binary, a ComfyUI API
client, a bash script, or Bend2. Two implementations of the same stage are
compared by the same oracle on the same pack.

## Invocation

```text
stages/<stage-id>/<impl>/run --in <pack-dir> --out <out-dir> --params <params.json>
```

- `<stage-id>` matches `^s[0-9]+-[a-z0-9-]+$` (`s0-identity`, `s1-fuse`, `s2-develop`, `s3-edit`, `s4-score`).
- `<impl>` is a directory per implementation (`bash`, `python-cuda`, `bend2`, `vkdt`, ...); its name lands in `result.json.impl`.
- `run` is executable, self-contained (a shell wrapper may activate a venv or call `docker run`).
- `<pack-dir>` is read-only for the stage; anything written there is a contract violation.
- `<out-dir>` exists and is empty when the stage starts; the stage owns it.
- `<params.json>` is stage-specific; absent → defaults. A stage must not read parameters from anywhere else.

## Exit and result

- Exit `0` and `<out-dir>/result.json` valid against `$defs/StageResult` in
  `shared/pack-schema/src/main/resources/rawpack/pack.schema.json`, with `ok: true`.
- Any non-zero exit, or a missing/invalid `result.json`, is a failed job. A stage
  that failed **should** still write `result.json` with `ok: false` and `notes`
  when it can — the orchestrator records both.
- `inputs_sha256` = sha256 of `<pack-dir>/manifest.json` (ties the result to one exact pack).
- Every file the stage produces and wants recorded appears in `outputs[]` with its sha256; unlisted files are ignored by the orchestrator.
- `metrics.wall_s` is mandatory; `gpu_s` when measured, else `null` — never estimated.

## Rules that keep the bench honest

1. No network access during `run` (models and weights are fetched at build/install time, not at run time).
2. Deterministic given the same inputs and params where the algorithm allows; when it does not (diffusion seeds), the seed is a param and lands in `notes`.
3. A stage never reads another stage's output except through `--in` (the orchestrator materialises chained inputs as a pack-like directory).
4. Timeouts are the orchestrator's job (`bin/with-timeout` semantics); a stage does not spawn detached processes.

## Reference implementation

`stages/s0-identity/bash/run` copies `manifest.json`, computes the hashes and
writes a valid `result.json`. It exists so the orchestrator, the bench and any
new language can be proven against the contract before real work exists.
