# S01 Domain Schema Package

## Objective

Implement `packages/domain-schema`: define the domain models with Pydantic v2 (`gpu_spec`, `cpu_spec`, `model_arch`, `quant_profile`, `benchmark_scenario`, `benchmark_metrics`), and export the JSON Schema of the Benchmark Report (contract version 0.9.0, see Section 9.3 of the plan), serving as the single contract between the CLI and the submission API.

## Dependencies

- **S00** (Repo Foundation): depends on the root-level uv / pytest project and the `make test` entry point.

## Wave

W1

## Deliverables

| Path | Content |
|---|---|
| `packages/domain-schema/pyproject.toml` | Package configuration (depends on Pydantic v2) |
| `packages/domain-schema/src/gpu_spec.py` | GPU spec model (corresponds to `gpu_model` in Section 10.1) |
| `packages/domain-schema/src/cpu_spec.py` | CPU spec model (corresponds to `cpu_model` in Section 10.1) |
| `packages/domain-schema/src/model_arch.py` | Model architecture model (corresponds to the Section 10.4 model catalog and the `model_architecture` enum) |
| `packages/domain-schema/src/quant_profile.py` | Quantization profile model (corresponds to Section 10.5 and the `quant_format` enum) |
| `packages/domain-schema/src/benchmark_scenario.py` | Benchmark scenario model (corresponds to Section 10.7) |
| `packages/domain-schema/src/benchmark_metrics.py` | Benchmark metrics model (corresponds to Section 10.9 and the `metric_kind` enum) |
| `packages/domain-schema/src/benchmark_report.py` | Report root model (contract 0.9.0, Section 9.3) |
| `packages/domain-schema/src/__init__.py` | Aggregate exports |
| `packages/domain-schema/schema/benchmark_report.v0.9.0.json` | Versioned exported JSON Schema (under version control) |
| `packages/domain-schema/tests/` | pytest unit tests |

## Requirements

- **R-1** Each domain model maps to a Section 10 entity of the plan: `gpu_spec` ↔ 10.1 `gpu_model`, `cpu_spec` ↔ 10.1 `cpu_model`, `model_arch` ↔ 10.4, `quant_profile` ↔ 10.5, `benchmark_scenario` ↔ 10.7, `benchmark_metrics` ↔ 10.9.
- **R-2** Enum values must match Section 10: `hardware_class` (gpu/cpu/npu/integrated_gpu), `model_architecture` (dense/moe/multimodal), `quant_format` (fp16/bf16/fp8/int8/int4/awq/gptq/exl2/gguf_q2…gguf_q8), `runtime_engine` (llama_cpp/ollama/vllm/sglang/exllamav2/tensorrt_llm/mlx/lmstudio).
- **R-3** The Benchmark Report contract must match the Section 9.3 JSON example: `schema_version`, `run_id`, `runtime`, `runtime_version`, `hardware_fingerprint`, `scenario` (prompt_tokens/generated_tokens/batch_size/context_tokens), `metrics` (ttft_ms/prefill_tok_s/decode_tok_s/peak_vram_mib/power_watt_avg), `artifacts` (artifact_kind/sha256).
- **R-4** `schema_version` is fixed at `"0.9.0"`.
- **R-5** Fields use strong typing and validation constraints (e.g. `peak_vram_mib > 0`, `decode_tok_s >= 0`).
- **R-6** The JSON Schema is exported as a version-controlled file (`schema/benchmark_report.v0.9.0.json`), named with the contract version number.

## Acceptance Criteria

- [ ] `uv run pytest packages/domain-schema` passes fully.
- [ ] The exported JSON Schema is written to `packages/domain-schema/schema/benchmark_report.v0.9.0.json` and placed under version control.
- [ ] The Section 9.3 example report JSON can be successfully deserialized by the `benchmark_report` model (with a corresponding test).
- [ ] This package's tests can be triggered via `make test`.

## Language Note

Code, comments, identifiers, and commit messages must all be in English; this Spec is written in Chinese and serves only as planning context.
