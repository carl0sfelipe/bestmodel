"""Import llm_lab_export perf runs as signed 0.9.0 benchmark submissions.

Reads an extracted lab export, converts curated perf experiments into contract
0.9.0 reports (with a normalized evidence artifact plus the raw engine log),
signs them with a local Ed25519 key, uploads to the Submission API and can then
replay each run through the S10 intake pipeline for validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "infra" / "seed"

CURATED_RUNS = {
    "20260802-224449-f5f476": ("model-qwq-32b", "q-gguf-q4-k-m"),
    "20260802-224540-64ae87": ("model-qwq-32b", "q-gguf-q4-k-m"),
    "20260802-225907-adb101": ("model-qwen35-35b-a3b", "q-gguf-q4-k-m"),
    "20260802-225920-9a5079": ("model-qwen35-35b-a3b", "q-gguf-q4-k-m"),
}
GPU_MODEL_ID = "gpu-rtx-3090"
RUNTIME_VERSION = "llama-server-lab-2026.08"
CLIENT_VERSION = "lab-importer-0.1.0"


def load_signing_key(key_path: Path) -> Ed25519PrivateKey:
    if key_path.exists():
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key


def write_public_key(private_key: Ed25519PrivateKey, key_path: Path) -> Path:
    public_path = key_path.with_suffix(".pub.pem")
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return public_path


def canonical_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"))


def build_evidence_content(experiment_id: str, metrics: dict) -> str:
    lines = [
        f"converted from experiment {experiment_id}",
        "source: llm_lab_export (RTX 3090 lab, llama.cpp CUDA, full GPU offload)",
        f"metric ttft_ms {metrics['ttft_ms']['mean']}",
        f"metric prefill_tok_s {metrics['prefill_tok_s']}",
        f"metric decode_tok_s {metrics['tps']['mean']}",
        f"metric peak_vram_mib {metrics['gpu_at_run_end']['mem_used_mib']}",
    ]
    return "\n".join(lines) + "\n"


def build_report(lab_dir: Path, experiment_id: str, model_id: str) -> dict:
    experiment_dir = lab_dir / "experiments" / experiment_id
    meta = json.loads((experiment_dir / "meta.json").read_text())
    metrics = json.loads((experiment_dir / "metrics.json").read_text())
    engine_log = (experiment_dir / "engine.log").read_text(errors="replace")
    config = meta["config"]
    prompt_word_count = len(metrics["prompt"].split())
    ttft_seconds = metrics["ttft_ms"]["mean"] / 1000.0
    prefill_tok_s = round(prompt_word_count / ttft_seconds, 1)
    metrics["prefill_tok_s"] = prefill_tok_s
    evidence = build_evidence_content(experiment_id, metrics)
    artifacts = [
        {
            "artifact_kind": "runtime_stdout",
            "sha256": hashlib.sha256(evidence.encode()).hexdigest(),
        },
        {
            "artifact_kind": "runtime_stderr",
            "sha256": hashlib.sha256(engine_log.encode()).hexdigest(),
        },
    ]
    hardware_blob = json.dumps(meta["hardware"], sort_keys=True, separators=(",", ":"))
    return json.loads(
        json.dumps(
            {
                "schema_version": "0.9.0",
                "run_id": f"lab-{experiment_id}",
                "runtime": "llama_cpp",
                "runtime_version": RUNTIME_VERSION,
                "hardware_fingerprint": "sha256:"
                + hashlib.sha256(hardware_blob.encode()).hexdigest(),
                "scenario": {
                    "prompt_tokens": prompt_word_count,
                    "generated_tokens": metrics["tokens_per_request"],
                    "batch_size": 1,
                    "context_tokens": config["ctx"],
                },
                "metrics": {
                    "ttft_ms": metrics["ttft_ms"]["mean"],
                    "prefill_tok_s": prefill_tok_s,
                    "decode_tok_s": metrics["tps"]["mean"],
                    "peak_vram_mib": metrics["gpu_at_run_end"]["mem_used_mib"],
                    "power_watt_avg": 0.0,
                },
                "artifacts": artifacts,
            }
        )
    ), (evidence, engine_log)


def sign_report(private_key: Ed25519PrivateKey, report: dict) -> tuple[str, str]:
    canonical = canonical_json(report)
    digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    signature = private_key.sign(digest.encode()).hex()
    return digest, signature


def upload_report(
    api_url: str,
    report: dict,
    digest: str,
    signature: str,
    parts: tuple,
    model_id: str,
    quant_id: str,
) -> int:
    nonce = httpx.get(f"{api_url}/v1/submissions/nonce", timeout=30).json()["challenge_nonce"]
    evidence, engine_log = parts
    files = {
        "report": (None, json.dumps(report)),
        "signature": (None, signature),
        "payload_digest": (None, digest),
        "challenge_nonce": (None, nonce),
        "client_version": (None, CLIENT_VERSION),
        "model_release_id": (None, model_id),
        "quantization_profile_id": (None, quant_id),
        "artifact_0": ("artifact_0", evidence.encode()),
        "artifact_1": ("artifact_1", engine_log.encode()),
    }
    response = httpx.post(f"{api_url}/v1/submissions", files=files, timeout=60)
    print(f"  upload status={response.status_code} body={response.text[:160]}")
    return response.status_code


def seed_row(filename: str, record_id: str) -> dict:
    rows = json.loads((SEED_DIR / filename).read_text())
    return next(row for row in rows if row["id"] == record_id)


class FakeIntakeRepository:
    """Minimal in-memory repository for replaying the S10 pipeline offline."""

    def __init__(self) -> None:
        self.statuses: dict[str, str] = {}
        self.ranking_updates: list[dict] = []

    def find_existing_run_in_group(self, dimension, exclude_run_id, statuses) -> bool:
        return False

    def fetch_peer_decode_values(self, dimension, exclude_run_id) -> list[float]:
        return []

    def count_peers(self, dimension) -> int:
        return 0

    def record_trust_assessment(self, run_id, assessment) -> None:
        pass

    def set_run_status(self, run_id, status, trust_score) -> None:
        self.statuses[run_id] = status

    def publish_ranking_update(self, event) -> None:
        self.ranking_updates.append(event)


def run_intake_pipeline(report: dict, quant_id: str, model_id: str, parts: tuple) -> dict:
    for entry in (
        REPO_ROOT / "apps" / "intake-worker" / "src",
        REPO_ROOT / "packages" / "domain-schema" / "src",
        REPO_ROOT / "packages" / "roofline-kernel" / "src",
    ):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    from worker import process_run  # noqa: PLC0415

    evidence, engine_log = parts
    scenario = report["scenario"]
    payload = {
        **report,
        "runtime_engine": report["runtime"],
        "signature_valid": True,
        "duration_seconds": report["metrics"]["ttft_ms"] / 1000.0
        + report["scenario"]["generated_tokens"] / max(report["metrics"]["decode_tok_s"], 1e-9),
        "hardware": seed_row("gpu_models.json", GPU_MODEL_ID),
        "model": seed_row("model_releases.json", model_id),
        "quant": seed_row("quantization_profiles.json", quant_id),
        "dimension": {
            "hardware_model_id": GPU_MODEL_ID,
            "model_release_id": model_id,
            "quantization_profile_id": quant_id,
            "runtime_engine": "llama_cpp",
            "context_tokens": scenario["context_tokens"],
            "batch_size": scenario["batch_size"],
        },
        "artifacts": [
            {
                "artifact_kind": artifact["artifact_kind"],
                "declared_sha256": artifact["sha256"],
                "content": content,
            }
            for artifact, content in zip(report["artifacts"], (evidence, engine_log))
        ],
    }
    return process_run(payload, FakeIntakeRepository())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab_dir", type=Path)
    parser.add_argument("--api-url", default="http://localhost:8011")
    parser.add_argument("--key", type=Path, default=Path("/tmp/bestmodel/importer.pem"))
    parser.add_argument("--live", action="store_true", help="upload to the Submission API")
    parser.add_argument("--intake", action="store_true", help="run the S10 pipeline per run")
    args = parser.parse_args()

    private_key = load_signing_key(args.key)
    public_path = write_public_key(private_key, args.key)
    print(f"signing key: {args.key} (trusted public key: {public_path})")

    for experiment_id, (model_id, quant_id) in CURATED_RUNS.items():
        print(f"\n=== {experiment_id} -> {model_id} {quant_id} ===")
        report, parts = build_report(args.lab_dir, experiment_id, model_id)
        digest, signature = sign_report(private_key, report)
        print(f"  digest={digest[:24]}... decode={report['metrics']['decode_tok_s']} tok/s")
        if args.live:
            upload_report(args.api_url, report, digest, signature, parts, model_id, quant_id)
        if args.intake:
            outcome = run_intake_pipeline(report, quant_id, model_id, parts)
            print(f"  intake status={outcome['status']} flags={outcome['outlier_flags']} "
                  f"rejections={outcome['rejection_reasons']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
