"""Duplicate submission detection on the dimension group (plan section 12.4).

A run is a duplicate when the dimension group already holds a validated or
quarantined run; new duplicates are rejected.
"""

from __future__ import annotations

from worker_models import DimensionGroup

DUPLICATE_REJECTION = "duplicate_submission"
BLOCKING_STATUSES = ("validated", "quarantined")


def detect_duplicate_submission(
    repository, dimension: DimensionGroup, exclude_run_id: str
) -> bool:
    return repository.find_existing_run_in_group(
        dimension, exclude_run_id=exclude_run_id, statuses=BLOCKING_STATUSES
    )
