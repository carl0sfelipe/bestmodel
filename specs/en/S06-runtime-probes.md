# S06: Runtime Probes (runtime-probes)

## Objective

Implement in `packages/runtime-probes` the standard Probe protocol plus two adapter probes for llama.cpp / Ollama: execute standardized scenarios per Section 9.3 of the plan and collect TTFT / Prefill / Decode / VRAM / Power metrics by parsing runtime stdout. Third-party runtime invocation is allowed only in the adapter layer; tests uniformly use fake runtimes (stdout fixtures).

## Dependencies

- S01 (domain-schema: `BenchmarkScenario`, `BenchmarkMetrics` data structures)

## Wave

W2

## Deliverables

| Path | Description |
|---|---|
| `packages/runtime-probes/pyproject.toml` | Package metadata and dependency declaration (depends on domain-schema) |
| `packages/runtime-probes/src/probe.py` | Standard Probe protocol, `Scenario` / `ProbeResult` data classes |
| `packages/runtime-probes/src/stdout_parser.py` | Pure-function stdout parsing (llama.cpp / Ollama) |
| `packages/runtime-probes/src/llama_cpp_probe.py` | llama.cpp adapter probe |
| `packages/runtime-probes/src/ollama_probe.py` | Ollama adapter probe |
| `packages/runtime-probes/tests/fixtures/llama_cpp_stdout.txt` | llama.cpp fake stdout fixture |
| `packages/runtime-probes/tests/fixtures/ollama_stdout.txt` | Ollama fake stdout fixture |
| `packages/runtime-probes/tests/fake_runtime.py` | fake runtime (injects fixture stdout) |
| `packages/runtime-probes/tests/test_stdout_parser.py` | Parser unit tests |
| `packages/runtime-probes/tests/test_llama_cpp_probe.py` | llama.cpp probe tests |
| `packages/runtime-probes/tests/test_ollama_probe.py` | Ollama probe tests |

## Technical Requirements

References Section 9.3 (from the original internal design doc) (CLI Benchmark Engine design) and Section 9.2 (module decomposition: `runtime-probes` is the adapter layer for llama.cpp/vLLM/Ollama).

### Probe Protocol

All probes implement a uniform interface (see `src/probe.py`):

```python
class Probe(Protocol):
    runtime: str
    def run(self, scenario: BenchmarkScenario) -> ProbeResult: ...
```

`ProbeResult` contains at least: `runtime`, `runtime_version`, `metrics` (`ttft_ms`, `prefill_tok_s`, `decode_tok_s`, `peak_vram_mib`, `power_watt_avg`) and the raw stdout (for use by artifacts).

### Standardized Scenario (9.3)

The probe executes a scenario: `prompt_tokens`, `generated_tokens`, `batch_size`, `context_tokens`. The llama.cpp probe maps the scenario to `llama-cli` arguments (`--n-predict`, `--ctx-size`, etc.); the Ollama probe uses the `--verbose` output of `ollama run` or the `timings` fields of `/api/generate`.

### stdout Parsing (9.3 structured output)

- `llama_cpp_probe.py`: parses the prefill / eval / `tokens_per_second` / KV cache / VRAM related lines in llama.cpp `--verbose` output.
- `ollama_probe.py`: parses `load_ns`, `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration` from `ollama --verbose` output, converting them to `ttft_ms`, `prefill_tok_s`, `decode_tok_s`.

### Isolation (9.2 adapter layer)

- Direct invocation of third-party processes (`llama-cli`, `ollama`) is allowed only inside the adapter files (`llama_cpp_probe.py`, `ollama_probe.py`).
- The `probe.py` protocol and `stdout_parser.py` parsing logic must not depend on third-party commands and must be generic across any runtime.
- Tests must not invoke real third-party binaries; they uniformly inject fake-runtime fixture stdout.

## Acceptance Criteria

1. Parser unit tests: given known output in the fixtures, assert deterministic `ttft_ms`, `prefill_tok_s`, `decode_tok_s` (exact assertions against known values)
2. Probe tests inject fixture stdout through the fake runtime and assert `ProbeResult.metrics` matches the fixture
3. stdout that is invalid or missing fields must not crash; it raises a clear exception identifying the runtime
4. All executable commands pass:

```bash
uv run pytest packages/runtime-probes/tests/test_stdout_parser.py -q
uv run pytest packages/runtime-probes/tests/test_llama_cpp_probe.py -q
uv run pytest packages/runtime-probes/tests/test_ollama_probe.py -q
uv run pytest packages/runtime-probes/tests -q
```

## Notes

Code, comments, and commit messages must all be in English. `vllm_probe.py` / `exllamav2_probe.py` are out of scope for this wave and left to later stories. Tests are uniformly triggered by `make test`, and `make test` must cover this package's (`packages/runtime-probes`) tests.
