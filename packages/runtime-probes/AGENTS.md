# packages/runtime-probes — Map

Standardized benchmark execution against real engines, parsed from engine output.

| Module | Content |
|---|---|
| `probe.py` | `Probe` protocol, `ProbeResult` (metrics + raw stdout) |
| `stdout_parser.py` | pure parsing functions (llama.cpp verbose / Ollama timings); no third-party deps |
| `llama_cpp_probe.py` | adapter: scenario → llama-cli args; ONLY place allowed to spawn llama-cli |
| `ollama_probe.py` | adapter: ollama run --verbose / /api/generate timings; ONLY place allowed to spawn ollama |
| `tests/fixtures/*.txt` | fake engine stdout with known values (exact assertions) |

Design rule: probes never hit real binaries in tests (fake runtime injection).
The Rust CLI (`cli/benchmark-probe`) reimplemented this parsing natively — when
engine output formats change, update BOTH sides (grep `tokens_per_second` /
`eval duration` across the repo).
Future (Phase 1): vllm/exllamav2 adapters were explicitly deferred (spec S06 note).
