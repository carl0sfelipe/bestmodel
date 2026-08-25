# packages/domain-schema — Map

Contract + domain models (Pydantic v2). Everything else depends on this.

| Module | Content |
|---|---|
| `benchmark_report.py` | `BenchmarkReport` root (contract 0.9.0), enums RuntimeEngine/ArtifactKind; runtime coercion `llama.cpp`→`llama_cpp` (intentional) |
| `benchmark_metrics.py` | metrics + `MetricKind` enum (incl. reserved kinds: peak_ram_mib, temperature_c_max, energy_joule) |
| `benchmark_scenario.py` | scenario (prompt/generated/batch/context) |
| `gpu_spec.py` / `cpu_spec.py` | hardware specs (plan §10.1) |
| `model_arch.py` | model + `ModelArchitecture` (dense/moe/multimodal) |
| `quant_profile.py` | quant + `QuantFormat` (14 values) + `KvCacheFormat` |
| `schema/benchmark_report.v0.9.0.json` | versioned exported JSON Schema (regenerate + bump version on contract change) |

Tests pin: the §9.3 example report parses verbatim; constraint violations raise;
enum values exact; exported schema matches `model_json_schema()`.
Contract evolution: 0.9.1 additive blocks (`statistics`/`tuning`/`spec_decode`/
`peak_ram_mib`) — spec `specs/en/L01-cli-v2-local-lab.md` §contract.
