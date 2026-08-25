# S05: Decode and Prefill Throughput Prediction (roofline-kernel)

## Objective

Implement the two core modules of Decode and Prefill throughput prediction in `packages/roofline-kernel`, turning the roofline models from Sections 11.3/11.4 and the pseudocode from Sections 11.5/11.6 of the plan into testable Python code, providing a deterministic throughput estimation baseline for the subsequent recommendation engine and CLI (S07).

## Dependencies

- S01 (domain-schema: `GpuSpec`, `ModelArch`, `QuantProfile`, `BenchmarkScenario` data structures)

## Wave

W2

## Deliverables

| Path | Description |
|---|---|
| `packages/roofline-kernel/pyproject.toml` | Package metadata and dependency declaration (depends on domain-schema) |
| `packages/roofline-kernel/src/estimate_decode_throughput.py` | Decode prediction implementation (exports `estimate_decode_tokens_per_second`) |
| `packages/roofline-kernel/src/estimate_prefill_throughput.py` | Prefill and TTFT prediction implementation (exports `estimate_prefill_tokens_per_second`, `estimate_ttft`) |
| `packages/roofline-kernel/tests/test_estimate_decode_throughput.py` | Decode unit tests |
| `packages/roofline-kernel/tests/test_estimate_prefill_throughput.py` | Prefill / TTFT unit tests |
| `packages/roofline-kernel/tests/hardware_fixtures.py` | Known-hardware fixtures (nominal bandwidth, compute capacity) |

## Technical Requirements

References Section 11.3 (Decode Roofline), Section 11.4 (Prefill Roofline), Section 11.5 (pseudocode: Decode prediction), and Section 11.6 (pseudocode: Prefill prediction) (from the original internal design doc).

### Effective Bandwidth (11.3)

\[
BW_{eff} = BW_{nominal} \times U_{runtime} \times U_{quant} \times U_{tp}
\]

- `U_runtime`: runtime utilization
- `U_quant`: quantization read efficiency
- `U_tp`: efficiency after multi-GPU communication penalty (e.g. the communication overhead factor introduced by all-reduce under tensor parallelism)

### Bytes Read per Decode Step (11.3)

\[
D_{bytes} = W_{step} + KV_{read}
\]

- Single-batch approximation: `W_step ≈ W_bytes_active`; `KV_read ≈ K_token × S`
- Multi-batch: `W_step_batch = W_shared + W_experts_distinct`; `KV_read_batch = K_token × S × B`

### Decode Step Time and tok/s (11.3)

\[
T_{step} = \frac{D_{bytes}}{BW_{eff}} + T_{allreduce}
\]

\[
Decode = \frac{B}{T_{step}}
\]

where `T_allreduce` is the per-step all-reduce communication latency in multi-GPU scenarios (0 for single GPU).

### Prefill FLOPs and Attention (11.4)

\[
F_{prefill} = 2 \times P_{active} \times S + F_{attention}
\]

\[
F_{attention} = 2 \times L \times H \times S^2 \times d_h
\]

\[
F_{token} = \frac{F_{prefill}}{S}
\]

### Effective Compute Capacity, Prefill tok/s and TTFT (11.4)

\[
C_{eff} = C_{nominal} \times U_{compute}
\]

\[
Prefill = \frac{C_{eff}}{F_{token}}
\]

\[
TTFT = \frac{S_{prompt}}{Prefill} + O_{latency}
\]

### Pseudocode Contract (11.5 / 11.6)

`estimate_decode_throughput.py` exports `estimate_decode_tokens_per_second(hardware, model, quant, scenario) -> float`:

- Internally implements `derive_effective_bandwidth_bytes_per_second(hardware, quant, scenario)` and `derive_decode_bytes_per_step(model, quant, scenario)`
- Raises `ValueError` when `bytes_per_generation_step <= 0`, message format: `bytes_per_generation_step={...}, expected > 0 bytes`

`estimate_prefill_throughput.py` exports `estimate_prefill_tokens_per_second(hardware, model, quant, scenario) -> float` and `estimate_ttft(...)`:

- Internally implements `derive_effective_flops(hardware, quant, scenario)` and `derive_prefill_flops_per_token(model, scenario)`
- Raises `ValueError` when `flops_per_prompt_token <= 0`, message format: `flops_per_prompt_token={...}, expected > 0 FLOPs`

## Acceptance Criteria

1. Unit tests use known-hardware fixtures (e.g. A100 80GB nominal bandwidth 2039 GB/s, H100 80GB nominal bandwidth 3350 GB/s, RTX 4090 nominal bandwidth 1008 GB/s):
   - Predictions fall within hand-computed acceptable ranges (±10%)
   - Monotonicity: decode tok/s does not increase as context `S` grows; decode tok/s increases as batch `B` grows; TTFT increases as prompt grows
2. Raises `ValueError` when `bytes_per_generation_step <= 0`
3. Raises `ValueError` when `flops_per_prompt_token <= 0`
4. All executable commands pass:

```bash
uv run pytest packages/roofline-kernel/tests/test_estimate_decode_throughput.py -q
uv run pytest packages/roofline-kernel/tests/test_estimate_prefill_throughput.py -q
uv run pytest packages/roofline-kernel/tests -q
```

## Notes

Code, comments, and commit messages must all be in English. Variable names in the formulas must stay consistent with the plan (`BW_eff`, `D_bytes`, `F_prefill`, `F_attention`, etc.). Tests are uniformly triggered by `make test`, and `make test` must cover this package's (`packages/roofline-kernel`) tests.
