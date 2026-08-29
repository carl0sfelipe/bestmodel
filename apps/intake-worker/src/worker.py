"""Intake worker: consumes benchmark run events and runs the validation pipeline.

Pipeline order follows plan section 12: payload validation, evidence extraction,
roofline and memory plausibility, duplicate detection, robust z-score, trust
assessment, then a ranking update notification. Status transitions:
``submitted -> validated | quarantined | rejected``.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from calculate_modified_zscore import check_statistical_plausibility
from calculate_trust_assessment import calculate_trust_assessment
from check_memory_plausibility import check_memory_plausibility
from check_roofline_plausibility import check_roofline_plausibility
from detect_duplicate_submission import DUPLICATE_REJECTION, detect_duplicate_submission
from extract_runtime_evidence import extract_runtime_evidence
from publish_ranking_update import publish_ranking_update
from settle_claims import settle_claims_for_run
from validate_submission_payload import validate_submission_payload
from worker_models import DimensionGroup, RunRecord, build_run_record, scenario_is_video

STATUS_VALIDATED = "validated"
STATUS_QUARANTINED = "quarantined"
STATUS_REJECTED = "rejected"

STREAM_KEY = "benchmark_runs"
CONSUMER_GROUP = "intake-workers"


class IntakeRepository(Protocol):
    """Data access surface the pipeline needs; fakes implement it in tests."""

    def find_existing_run_in_group(
        self, dimension: DimensionGroup, exclude_run_id: str, statuses: tuple[str, ...]
    ) -> bool: ...

    def fetch_peer_decode_values(
        self, dimension: DimensionGroup, exclude_run_id: str
    ) -> list[float]: ...

    def count_peers(self, dimension: DimensionGroup) -> int: ...

    def record_trust_assessment(self, run_id: str, assessment: dict[str, float]) -> None: ...

    def set_run_status(self, run_id: str, status: str, trust_score: float) -> None: ...

    def fetch_settlement_context(self, run_id: str) -> dict[str, Any] | None:
        """Open claim bound to this run: id, claimant, vote margin, points."""
        ...

    def complete_claim_settlement(
        self,
        claim_id: str,
        claimant_id: str,
        events: list[tuple[str, int]],
        new_points: int,
        new_tier: str,
    ) -> None:
        """Settle the claim and credit reputation events atomically."""
        ...

    def publish_ranking_update(self, event: dict[str, Any]) -> None: ...

    def fetch_run_payload(self, run_id: str) -> dict[str, Any] | None:
        """Hydrate a complete run payload from storage for minimal queue events."""
        ...


def process_run(payload: dict[str, Any], repository: IntakeRepository) -> dict[str, Any]:
    record = build_run_record(payload)
    rejection_reasons = validate_submission_payload(record)
    rejection_reasons.extend(extract_runtime_evidence(record))
    outlier_flags: list[str] = []
    if not rejection_reasons:
        _collect_plausibility_flags(record, outlier_flags)
        if detect_duplicate_submission(repository, record.dimension, record.run_id):
            rejection_reasons.append(DUPLICATE_REJECTION)
        if not rejection_reasons:
            _collect_statistical_flag(record, repository, outlier_flags)
    status = _decide_status(rejection_reasons, outlier_flags)
    assessment = calculate_trust_assessment(
        record, outlier_flags, repository.count_peers(record.dimension)
    )
    assessment["outlier_flags"] = list(outlier_flags)
    repository.record_trust_assessment(record.run_id, assessment)
    repository.set_run_status(record.run_id, status, assessment["final_score"])
    settlement = settle_claims_for_run(repository, record.run_id, status)
    publish_ranking_update(repository, record.run_id, status, assessment["final_score"])
    return {
        "run_id": record.run_id,
        "status": status,
        "rejection_reasons": rejection_reasons,
        "outlier_flags": outlier_flags,
        "trust_assessment": assessment,
        "claim_settlement": settlement,
    }


def _collect_plausibility_flags(record: RunRecord, outlier_flags: list[str]) -> None:
    if not record.hardware:
        # Community submissions without a bound catalog GPU cannot be checked
        # against hardware limits; plausibility runs once hardware is bound.
        return
    if scenario_is_video(record):
        # The roofline and memory models are token-based (LLM); video runs are
        # held by signature + evidence + duration consistency until a video
        # roofline refit lands (Story 1.4 follow-up).
        return
    roofline_flag = check_roofline_plausibility(record)
    if roofline_flag:
        outlier_flags.append(roofline_flag)
    memory_flag = check_memory_plausibility(record)
    if memory_flag:
        outlier_flags.append(memory_flag)


def _collect_statistical_flag(
    record: RunRecord, repository: IntakeRepository, outlier_flags: list[str]
) -> None:
    if scenario_is_video(record):
        return  # peer decode tok/s is meaningless for clip runs
    peer_values = repository.fetch_peer_decode_values(record.dimension, record.run_id)
    statistical_flag = check_statistical_plausibility(record, peer_values)
    if statistical_flag:
        outlier_flags.append(statistical_flag)


def _decide_status(rejection_reasons: list[str], outlier_flags: list[str]) -> str:
    if rejection_reasons:
        return STATUS_REJECTED
    if outlier_flags:
        return STATUS_QUARANTINED
    return STATUS_VALIDATED


def process_event_message(
    message: dict[str, Any], repository: IntakeRepository
) -> dict[str, Any]:
    """Handle one stream message: either a self-contained run payload under
    ``data`` or a minimal event carrying a ``run_id`` to hydrate from storage."""
    fields = {
        (key.decode() if isinstance(key, bytes) else str(key)): (
            value.decode() if isinstance(value, bytes) else value
        )
        for key, value in message.items()
    }
    if "data" in fields:
        payload = json.loads(fields["data"])
    elif "run_id" in fields:
        payload = repository.fetch_run_payload(fields["run_id"])
        if payload is None:
            return {
                "run_id": fields["run_id"],
                "status": STATUS_REJECTED,
                "rejection_reasons": ["run_not_found"],
                "outlier_flags": [],
                "trust_assessment": {},
            }
    else:
        return {
            "run_id": None,
            "status": STATUS_REJECTED,
            "rejection_reasons": ["malformed_event"],
            "outlier_flags": [],
            "trust_assessment": {},
        }
    return process_run(payload, repository)


def consume_pending_events(
    redis_client: Any,
    repository: IntakeRepository,
    stream_key: str = STREAM_KEY,
    group: str = CONSUMER_GROUP,
    consumer: str = "worker-1",
    count: int = 10,
    block_ms: int = 1000,
) -> list[dict[str, Any]]:
    """Read one batch of stream messages, process them and acknowledge each."""
    _ensure_consumer_group(redis_client, stream_key, group)
    response = redis_client.xreadgroup(
        group, consumer, {stream_key: ">"}, count=count, block=block_ms
    )
    outcomes: list[dict[str, Any]] = []
    for _stream, messages in response or []:
        for message_id, fields in messages:
            outcome = process_event_message(fields, repository)
            redis_client.xack(stream_key, group, message_id)
            outcomes.append(outcome)
    return outcomes


def _ensure_consumer_group(redis_client: Any, stream_key: str, group: str) -> None:
    try:
        redis_client.xgroup_create(stream_key, group, id="0", mkstream=True)
    except Exception:
        pass


def run_worker_loop(repository: IntakeRepository, redis_client: Any, idle_sleep_seconds: float = 1.0) -> None:
    """Consume the benchmark stream until interrupted."""
    while True:
        outcomes = consume_pending_events(redis_client, repository)
        for outcome in outcomes:
            print(
                f"intake: run={outcome['run_id']} status={outcome['status']} "
                f"flags={outcome['outlier_flags']} reasons={outcome['rejection_reasons']}",
                flush=True,
            )
        if not outcomes:
            time.sleep(idle_sleep_seconds)


def main() -> int:
    import redis

    from postgres_repository import PostgresIntakeRepository

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6380/0")
    redis_client = redis.Redis.from_url(redis_url)
    repository = PostgresIntakeRepository(redis_client=redis_client)
    print(f"intake worker started (stream={STREAM_KEY}, group={CONSUMER_GROUP})", flush=True)
    try:
        run_worker_loop(repository, redis_client)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
