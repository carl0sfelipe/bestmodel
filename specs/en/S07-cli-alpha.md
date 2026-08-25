# S07: CLI alpha (benchmark-probe)

## Goal

Implement the CLI alpha in `cli/benchmark-probe` (Rust): detect system topology, detect installed runtimes, execute standardized scenarios, parse runtime output, and produce Plain Text user output. Invoke locally installed llama.cpp / Ollama, conforming to the directory structure in Section 15 and the output constraints in Section 9.3 of the plan.

## Dependencies

- S06 (runtime-probes: metric semantics and stdout parsing baseline)

## Wave

W3

## Deliverables

| Path | Description |
|---|---|
| `cli/benchmark-probe/Cargo.toml` | Cargo manifest (edition, dependencies, binary name `benchmark-probe`) |
| `cli/benchmark-probe/src/main.rs` | Entry point: CLI argument parsing (`--help`, `--runtime`, `--model`, etc.) and flow orchestration |
| `cli/benchmark-probe/src/collect_system_topology.rs` | Collect GPU model / VRAM / driver / OS information |
| `cli/benchmark-probe/src/detect_runtime_installations.rs` | Detect local llama.cpp / Ollama installations and versions |
| `cli/benchmark-probe/src/execute_benchmark_scenario.rs` | Invoke runtime to execute standardized scenario |
| `cli/benchmark-probe/src/parse_runtime_output.rs` | Parse runtime stdout, produce metrics |
| `cli/benchmark-probe/tests/cli_smoke.rs` | Smoke integration test (fixture / mock runtime) |

## Technical Requirements

Reference Section 15 (from the original internal design doc) (code repository / Monorepo directory structure, `cli/benchmark-probe`) and Section 9.3 (CLI Benchmark Engine design).

### Directory and modules (15)

Module responsibilities are split according to the directory structure:

- `main.rs`: entry point and CLI argument parsing
- `collect_system_topology.rs`: hardware and system environment detection (CLI responsibility 1)
- `detect_runtime_installations.rs`: installed runtime detection (CLI responsibility 2)
- `execute_benchmark_scenario.rs`: execute standardized scenario (CLI responsibility 4)
- `parse_runtime_output.rs`: parse runtime stdout and extract metrics (CLI responsibility 5)

This wave does not include `sign_submission_payload.rs` or `upload_benchmark_report.rs` (signing and uploading are deferred to a later story).

### Standardized scenario execution (9.3)

`execute_benchmark_scenario.rs` invokes locally installed llama.cpp (`llama-cli`, etc.) or Ollama (`ollama run`) to execute the standardized scenario (`prompt_tokens`, `generated_tokens`, `batch_size`, `context_tokens`). When a runtime is not installed, output a clear error with installation hints and exit with a non-zero exit code.

### Plain Text output constraints (9.3)

User-visible output must be Plain Text only, formatted per the example in Section 9.3, e.g.:

```text
Running llama.cpp benchmark
Model: Qwen2.5-Coder-32B-Q4_K_M
Prompt tokens: 4096
Generated tokens: 512
TTFT: 812 ms
Prefill: 5041 tok/s
Decode: 18.7 tok/s
Peak VRAM: 21.3 GiB
```

### Tests

`tests/cli_smoke.rs` uses fixture / mock runtime (a script simulating stdout, not calling real third-party software) to verify argument parsing, runtime detection, and Plain Text output.

## Acceptance Criteria

1. Build and tests all pass:

```bash
cd cli/benchmark-probe && cargo build
cd cli/benchmark-probe && cargo test
```

2. `--help` works and outputs usage (argument names, descriptions, examples):

```bash
cd cli/benchmark-probe && cargo run -- --help
```

3. Smoke scenario against mock / fixture runtime runs successfully, stdout is Plain Text and includes TTFT / Prefill / Decode fields:

```bash
cd cli/benchmark-probe && cargo run -- --runtime mock
```

4. When runtime is not installed, output an error and return a non-zero exit code.

## Notes

Code, comments, and commit messages must be in English. Rust code follows `cargo fmt` and `cargo clippy` (if configured).
