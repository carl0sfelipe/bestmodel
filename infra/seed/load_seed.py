#!/usr/bin/env python3
"""Load seed catalog data into the bestmodel database.

Reads the JSON files in infra/seed and inserts them into the S02 tables in
dependency order: gpu_model -> model_release -> quantization_profile ->
inference_runtime. Idempotent via INSERT ... ON CONFLICT (id) DO NOTHING.

Connection string is read from the DATABASE_URL environment variable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

SEED_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://bestmodel:bestmodel@localhost:5434/bestmodel",
)

TABLES = [
    {
        "file": "gpu_models.json",
        "table": "gpu_model",
        "columns": [
            "id",
            "vendor",
            "marketing_name",
            "vram_mib",
            "memory_bandwidth_gib_s",
            "fp16_tflops",
            "int8_tops",
            "tdp_watt",
            "pcie_generation",
            "pcie_lane_width",
            "supports_nvlink",
            "released_at",
        ],
    },
    {
        "file": "model_releases.json",
        "table": "model_release",
        "columns": [
            "id",
            "family",
            "release_name",
            "architecture",
            "parameter_count_billion",
            "active_parameter_count_billion",
            "num_layers",
            "hidden_size",
            "num_attention_heads",
            "num_kv_heads",
            "head_dim",
            "expert_count",
            "experts_per_token",
            "max_context_tokens",
            "released_at",
        ],
    },
    {
        "file": "quantization_profiles.json",
        "table": "quantization_profile",
        "columns": [
            "id",
            "display_name",
            "weight_format",
            "weight_bits",
            "kv_cache_format",
            "kv_cache_bits",
            "group_size",
            "calibration_set",
            "expected_quality_retention",
        ],
    },
    {
        "file": "inference_runtimes.json",
        "table": "inference_runtime",
        "columns": [
            "id",
            "engine",
            "version",
            "supports_tensor_parallel",
            "supports_kv_cache_quant",
            "supports_cpu_offload",
        ],
    },
]


def main() -> int:
    for spec in TABLES:
        path = SEED_DIR / spec["file"]
        if not path.is_file():
            print(f"seed file not found: {path}", file=sys.stderr)
            return 1

        with path.open(encoding="utf-8") as fh:
            rows = json.load(fh)
        if not isinstance(rows, list):
            print(f"seed file is not a JSON array: {path}", file=sys.stderr)
            return 1

        columns = spec["columns"]
        quoted = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = (
            f"INSERT INTO {spec['table']} ({quoted}) VALUES ({placeholders}) "
            "ON CONFLICT (id) DO NOTHING"
        )
        values = [tuple(row.get(column) for column in columns) for row in rows]

        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_sql, values)

        print(f"loaded {len(rows)} rows into {spec['table']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
