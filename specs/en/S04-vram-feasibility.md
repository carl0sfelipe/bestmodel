# S04 — VRAM Feasibility Kernel (VRAM Footprint + Context Limit)

## Objective

Implement VRAM footprint and context limit prediction in `packages/roofline-kernel`, faithfully implementing the Section 11.2 and 11.7 formulas, serving as the feasibility-filtering kernel of the recommendation engine.

## Dependencies

- S01 (model/quantization/runtime data classes provided by `packages/domain-schema`; function signatures follow the S01 spec)

## Wave

W2

## Deliverables

- `packages/roofline-kernel/pyproject.toml`
- `packages/roofline-kernel/src/roofline_kernel/__init__.py`
- `packages/roofline-kernel/src/roofline_kernel/estimate_vram_footprint.py`
- `packages/roofline-kernel/src/roofline_kernel/estimate_context_limit.py`
- `packages/roofline-kernel/tests/test_estimate_vram_footprint.py`
- `packages/roofline-kernel/tests/test_estimate_context_limit.py`

## Technical Requirements

### Formulas (Section 11.2)

- Dense weights: `W_bytes = P × b_w / 8 × η_pack`
- MoE weights: `W_bytes_active = (P_shared + P_expert × E_active) × b_w / 8 × η_pack`; the implementation prefers `model.active_parameter_count_billion`, and when absent computes with `P_shared = P_total − P_expert × expert_count` and `E_active = experts_per_token`
- KV per token: `K_token = 2 × L × H_kv × d_h × b_kv` (one copy each for K and V)
- Total KV: `KV_total = K_token × S × B`
- Runtime overhead: `O_runtime = O_base + α × (W_bytes + KV_total)`
- Peak VRAM: `VRAM_peak = W_bytes + KV_total + O_runtime`
- Feasibility: `VRAM_peak ≤ VRAM_capacity × 0.95`

### Formulas (Section 11.7)

- `available_bytes = vram_capacity × safety_margin − weight_bytes − runtime_overhead`
- `max_context_tokens = floor(available_bytes / kv_bytes_per_token / batch_size)`
- Result capped at `model.max_context_tokens`
- When the target context is unreachable, return suggestions: maximum acceptable context, suggested KV cache quantization, suggested smaller quantization, suggested CPU offload, suggested larger-VRAM hardware

### Constants and Units

- Defaults: `η_pack = 1.05` (range 1.02–1.10), `safety_margin = 0.95`, `α = 0.05`
- Default runtime base: llama_cpp = 0.8 GiB, vllm = 2.0 GiB, others = 1.5 GiB
- Internally compute consistently in bytes; externally return peak VRAM in GiB (float) and max context as int

### Coding Standards (Section 14 engineering standards)

- Functions 4–20 lines, single file < 500 lines
- No ambiguous names (e.g. `data`, `handler`, `Manager`)
- Exceptions must carry the offending value and the expected format (e.g. `b_w` must be > 0)

## Acceptance Criteria

1. All tests pass:

   ```bash
   uv run pytest packages/roofline-kernel -v
   ```

2. Known cases (expected values use `pytest.approx`, float tolerance ±3%):

   **Case A (Dense, llama_cpp, 1× RTX 3090):**
   - Input: P=8e9, L=32, H_kv=8, d_h=128, b_w=4.5, η_pack=1.0, b_kv=2 (fp16), S=4096, B=1, runtime=llama_cpp, vram_capacity=24576 MiB, model.max_context_tokens=8192
   - Expected: `peak_vram_gib ≈ 5.73`; `is_feasible=True`; `max_context_tokens=8192` (capped by the model limit)

   **Note:** Case B uses vllm only to take its runtime base overhead (`O_base`); the Q4_K_M + vllm combination is a synthetic scenario for the kernel (the kernel is unaware of runtime and quantization details), and validation of real runtime/quantization combinations is left to the CLI.

   **Case B (32B Q4_K_M, vllm, 2× RTX 4090):**
   - Input: P=32.76e9, L=64, H_kv=8, d_h=128, b_w=4.5, η_pack=1.08, b_kv=2, S=8192, B=1, runtime=vllm, vram_capacity=2×24576=49152 MiB, model.max_context_tokens=131072
   - Expected: `peak_vram_gib ≈ 23.56`; `is_feasible=True`; `max_context_tokens=98468` and `>= 32000`

   **Case C (same 32B, only 1× RTX 4090, infeasible):**
   - Input same as Case B, vram_capacity=24576 MiB, target context=8192
   - Expected: `is_feasible=False`; `max_context_tokens=5072 < 8192`; suggestion list non-empty (includes "maximum acceptable context" and at least one mitigation suggestion)

3. Exception paths: invalid values such as `b_w`, `vram_capacity`, `batch_size` raise exceptions carrying the offending value.
4. Code, comments, and commit messages must all be in English.

## Notes

- Implement strictly per the formulas; do not add extra heuristics.
- This story implements only the VRAM and context kernels; decode/prefill prediction and quality decay belong to later stories.
- Do not run git commit.
