#!/usr/bin/env python3
"""Simulate the Story 1.4 video cells with the roofline estimator (Story 3.1).

The real Story 1.4 measures Wan 2.2 14B FLF2V on the owner's 6x3090 rig. Until
that run happens, this script keeps the corpus/recommender pipeline exercisable
by inserting DERIVED cells (source_class='derived') computed from the gpu_model
catalog specs plus the roofline diffusion estimator. Derived cells are never
`measured_signed`; when the real run lands, the same deterministic ids are
re-upserted with measured numbers and class.

Idempotent: every id is uuid5-derived; re-running refreshes values in place.

DECLARED GAPS (verify before public exposure):
- Wan 2.2 14B architecture constants (40 layers, hidden 5120, 14B active,
  released 2025-07) come from the recipe research, NOT from the HF
  config.json — confirm before trusting cross-model comparisons.
- ATTENTION_QUADRATIC_FRACTION is the calibration knob; refit against the
  real 6x3090 cells.

Usage:
    DATABASE_URL=... uv run python infra/scripts/simulate_video_cells.py \
        [--export /tmp/derived_runs.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "domain-schema" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "roofline-kernel" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "roofline-kernel" / "tests"))

from estimate_diffusion_step import DiffusionWorkload, estimate_seconds_per_clip
from gpu_spec import GpuSpec

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://inference_vein:inference_vein@localhost:5434/inference_vein",
)

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
RECIPE_ID = "wan22-flf2v-720p-81f-v1"
MODEL_RELEASE_ID = "model-wan22-i2v-flf2v-14b"
FRAMES = 81
STEPS = 20
WIDTH = 1280
HEIGHT = 720
RUNTIME_ID = "comfyui"

# gpu_model catalog id -> weight path (bits, native fp8 support by architecture)
SIMULATED_GPUS = {
    "gpu-rtx-3090": {"weight_bits": 8.0, "has_native_fp8": False},  # sm86: Q8 dequant to fp16 compute
    "gpu-rtx-4090": {"weight_bits": 8.0, "has_native_fp8": True},   # sm89: fp8 scaled
}


def derived_id(kind: str, *parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "sim:" + kind + ":" + ":".join(parts)))


def workload_for(weight_bits: float, has_native_fp8: bool) -> DiffusionWorkload:
    return DiffusionWorkload(
        width=WIDTH,
        height=HEIGHT,
        frames=FRAMES,
        steps=STEPS,
        active_parameters_billion=14.0,
        num_layers=40,
        hidden_size=5120,
        weight_bits=weight_bits,
        has_native_fp8=has_native_fp8,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", default=None, help="write leaderboard-shaped runs JSON here")
    args = parser.parse_args()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, marketing_name, vram_mib, memory_bandwidth_gib_s, fp16_tflops, tdp_watt FROM gpu_model WHERE id = ANY(%s)", (list(SIMULATED_GPUS),))
            gpu_rows = {row[0]: row for row in cur.fetchall()}
            missing = set(SIMULATED_GPUS) - set(gpu_rows)
            if missing:
                print(f"gpu_model rows missing from catalog: {sorted(missing)}", file=sys.stderr)
                return 1

            scenario_id = derived_id("scenario", RECIPE_ID)
            cur.execute(
                """
                INSERT INTO benchmark_scenario
                (id, scenario_kind, width, height, frames, steps, cfg, shift, seed, tensor_parallel)
                VALUES (%s, 'video', %s, %s, %s, %s, 3.5, 5.0, 42, 1)
                ON CONFLICT (id) DO NOTHING
                """,
                (scenario_id, WIDTH, HEIGHT, FRAMES, STEPS),
            )

            cur.execute(
                """
                INSERT INTO model_release
                (id, family, release_name, architecture, parameter_count_billion,
                 num_layers, hidden_size, num_attention_heads, num_kv_heads, head_dim,
                 max_context_tokens, released_at)
                VALUES (%s, 'wan-2.2', 'Wan 2.2 I2V FLF2V 14B', 'dense', 14.0,
                        40, 5120, 40, 40, 128, 302400, '2025-07-25')
                ON CONFLICT (id) DO NOTHING
                """,
                (MODEL_RELEASE_ID,),
            )

            export_rows = []
            for gpu_id, config in SIMULATED_GPUS.items():
                row = gpu_rows[gpu_id]
                spec = GpuSpec(
                    id=row[0], vendor="nvidia", marketing_name=row[1], vram_mib=row[2],
                    memory_bandwidth_gib_s=float(row[3]), fp16_tflops=float(row[4]), tdp_watt=row[5],
                )
                workload = workload_for(config["weight_bits"], config["has_native_fp8"])
                seconds_per_clip = estimate_seconds_per_clip(spec, workload)
                it_per_s = STEPS / seconds_per_clip
                frames_per_s = FRAMES / seconds_per_clip

                hardware_id = derived_id("hardware", gpu_id)
                cur.execute(
                    """
                    INSERT INTO hardware_submission
                    (id, owner_account_id, gpu_model_id, gpu_count, ram_gib, os_name, os_version, environment_snapshot)
                    VALUES (%s, '00000000-0000-0000-0000-000000000001', %s, 1, 1, 'simulated', 'roofline', %s)
                    ON CONFLICT (id) DO UPDATE SET gpu_model_id = EXCLUDED.gpu_model_id
                    """,
                    (hardware_id, gpu_id, json.dumps({"source": "roofline-simulation-v1"})),
                )

                run_id = derived_id("run", gpu_id, RECIPE_ID)
                cur.execute(
                    """
                    INSERT INTO benchmark_run
                    (id, hardware_submission_id, model_release_id, quantization_profile_id,
                     inference_runtime_id, benchmark_scenario_id, status, client_version,
                     signature, payload_digest, recipe_id, source_class, seconds_per_clip,
                     it_per_s, frames_per_s, source_url)
                    VALUES (%s, %s, %s, 'q-fp16', %s, %s, 'validated', 'simulate-video-cells-1',
                            'derived', 'derived', %s, 'derived', %s, %s, %s,
                            'roofline:estimate_diffusion_step#v1')
                    ON CONFLICT (id) DO UPDATE SET
                      seconds_per_clip = EXCLUDED.seconds_per_clip,
                      it_per_s = EXCLUDED.it_per_s,
                      frames_per_s = EXCLUDED.frames_per_s
                    """,
                    (run_id, hardware_id, MODEL_RELEASE_ID, RUNTIME_ID, scenario_id,
                     RECIPE_ID, round(seconds_per_clip, 3), round(it_per_s, 6), round(frames_per_s, 6)),
                )
                print(
                    f"derived cell {gpu_id}: {seconds_per_clip/3600:.2f}h/clip "
                    f"({seconds_per_clip:.0f}s, it/s {it_per_s:.4f}, frames/s {frames_per_s:.4f})"
                )
                export_rows.append(
                    {
                        "run_id": run_id,
                        "gpu_model_id": gpu_id,
                        "model_release_id": MODEL_RELEASE_ID,
                        "recipe_id": RECIPE_ID,
                        "source_class": "derived",
                        "trust_score": None,
                        "age_days": 0.0,
                        "seconds_per_clip": round(seconds_per_clip, 3),
                        "frames_per_s": round(frames_per_s, 6),
                    }
                )

    if args.export:
        Path(args.export).write_text(json.dumps(export_rows, indent=2) + "\n", encoding="utf-8")
        print(f"exported {len(export_rows)} derived runs to {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
