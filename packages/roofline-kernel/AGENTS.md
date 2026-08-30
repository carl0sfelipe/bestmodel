# packages/roofline-kernel — Map

Physics-based prediction core. Two import surfaces (historical; keep both):
package form `from roofline_kernel import ...` (VRAM/context) and flat form
`from estimate_decode_throughput import ...` (throughput).

| Module | Content |
|---|---|
| `roofline_kernel/estimate_vram_footprint.py` | §11.2: weights + KV + overhead; `VramFootprint` (peak bytes/GiB, feasible @ 0.95 margin); MoE active-weights preference |
| `roofline_kernel/estimate_context_limit.py` | §11.7: max context from available bytes; suggestions when unreachable |
| `estimate_decode_throughput.py` | §11.3/§11.5: BW_eff = BW×U_runtime×U_quant×U_tp; bytes/step; T_allreduce |
| `estimate_prefill_throughput.py` | §11.4/§11.6: FLOPs + attention term; TTFT |

Calibration constants (tune with measured data, coordinate via docs/findings.md):
U_RUNTIME=0.8, U_QUANT=0.9, U_TP=1.0, T_ALLREDUCE=0, ETA_PACK default 1.05,
safety margin 0.95, runtime base overhead {llama_cpp: 0.8 GiB, vllm: 2.0 GiB, other: 1.5 GiB}.

Real-data calibration status: VRAM P50 6.18% (harness:
`tests/regression/vram_error_harness.py`); decode ceiling tension F2; MoE gaps F3/F4/F5.


## Change checklist

- Touched a VRAM/throughput formula? The gate's VRAM-prediction criterion
  (P50 error < 10%) is the regression net — `make gate` in the same commit.
- Kernel constants feed the recommendation engine and the web estimator:
  formula change = engine tests + derived data regenerate (apps/web
  scripts/derive.mjs) in the same commit.

## Load-bearing decisions

- Prediction constants are calibrated against measured rig data (the gate
  prints predicted vs measured per model); do not "fix" a formula to make
  one cell pass — recalibrate with data.
