"""S26 pin: the fake leaderboard DERIVES from inserted rows (no canned list).

The guarantee under test is the death of the last fake==fake read
(direction v2, D3): a row only renders if the full chain was WRITTEN —
scenario + quant + runtime (INNER), validated status, classified source —
and the rendered values come from the stored row, not from a test-supplied
answer. The Postgres side of this contract is the real SELECT, exercised
end to end by the gate's video leg (make gate, section 6b).
"""

from __future__ import annotations

import uuid
from typing import Any

from fake_database import FakeDatabase


def _chain(database: FakeDatabase, *, run_id: str, status: str, source_class: str | None) -> None:
    hardware_id = str(uuid.uuid4())
    scenario_id = str(uuid.uuid4())
    database.insert_hardware_submission(
        {
            "id": hardware_id,
            "owner_account_id": "00000000-0000-0000-0000-000000000001",
            "gpu_model_id": "gpu-rtx-3090",
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 32,
            "os_name": "s26",
            "os_version": "0",
            "environment_snapshot": {"hardware_fingerprint": "sha256:" + "0" * 64},
        }
    )
    database.insert_scenario(
        {
            "id": scenario_id,
            "scenario_kind": "prompt",
            "tensor_parallel": 1,
            "prompt_tokens": 512,
            "generated_tokens": 128,
            "context_tokens": 4096,
            "batch_size": 1,
            "width": None,
            "height": None,
            "frames": None,
            "steps": None,
            "cfg": None,
            "shift": None,
            "seed": None,
        }
    )
    database.insert_benchmark_run(
        {
            "id": run_id,
            "hardware_submission_id": hardware_id,
            "model_release_id": "model-x",
            "quantization_profile_id": "q-fp16",
            "inference_runtime_id": "llama-cpp",
            "benchmark_scenario_id": scenario_id,
            "status": status,
            "client_version": "s26",
            "signature": "ff",
            "payload_digest": "sha256:" + "0" * 64,
            "signature_key_id": None,
            "recipe_id": None,
            "source_class": source_class,
            "seconds_per_clip": None,
            "it_per_s": None,
            "frames_per_s": None,
            "source_url": None,
        }
    )
    database.insert_benchmark_metric(
        {"benchmark_run_id": run_id, "kind": "decode_tok_s", "p50_value": 42.0, "unit": "tok/s"}
    )


def test_leaderboard_derives_from_written_rows_only() -> None:
    database = FakeDatabase()
    _chain(database, run_id="s26-validated", status="validated", source_class="measured_signed")
    _chain(database, run_id="s26-submitted", status="submitted", source_class="measured_signed")
    _chain(database, run_id="s26-unclassified", status="validated", source_class=None)

    # explicit timestamps: the read order is submitted_at DESC (the SELECT
    # contract); microsecond races between inserts would flake the pin.
    database.set_run_submitted_at("s26-validated", "2026-08-30T02:00:00+00:00")
    database.set_run_submitted_at("s26-unclassified", "2026-08-30T01:00:00+00:00")

    entries = database.fetch_leaderboard_entries()
    run_ids = [entry["run_id"] for entry in entries]

    # the SELECT contract: validated rows render (classified or not — the
    # source_class drop lives in the SERVICE layer, asserted below); the
    # submitted one never renders; the read answers what was WRITTEN.
    assert run_ids == ["s26-validated", "s26-unclassified"]

    from src.services.query_leaderboard import query_leaderboard

    service_ids = [run["run_id"] for run in query_leaderboard(database, {}, None, None, None)["runs"]]
    assert service_ids == ["s26-validated"]  # service drops unclassified (Story 2.1)

    entry: dict[str, Any] = entries[0]
    assert entry["source_class"] == "measured_signed"
    assert entry["decode_tok_s"] == 42.0
    assert entry["quant_format"] == "fp16"  # from the seed catalog, not a canned value
    assert entry["runtime_engine"] == "llama_cpp"
    assert entry["vram_capacity_mib"] == 24576  # gpu-rtx-3090 from the seed catalog
    assert entry["submitted_at"]  # DB-default applied on insert
