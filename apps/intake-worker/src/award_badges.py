"""Badges: the ladder's evidence, awarded when an act actually happens.

A badge says "you did this", so it may only be awarded by the thing that
happened — never computed from a score, never granted for joining.

Three acts can grant one today, and each one has a real owner in the
schema:

- ``first_verified_run`` — a run on YOUR machine was validated. The run's
  hardware submission names the account that owns that machine.
- ``claim_settler``     — a claim you filed became verified evidence.
- ``giant_killer``      — a report you filed was confirmed by a moderator.

The other two codes in the vocabulary (``pool_contributor_100h`` and
``rig_collector``) describe thresholds this code cannot read yet — there is
no run duration anywhere in the schema, and a rig count is a reading, not
an act. They stay unawarded rather than being granted on a guess.
"""

from __future__ import annotations

from typing import Any, Protocol

STATUS_VALIDATED = "validated"

BADGE_FIRST_VERIFIED_RUN = "first_verified_run"
BADGE_CLAIM_SETTLER = "claim_settler"
BADGE_GIANT_KILLER = "giant_killer"


class BadgeRepository(Protocol):
    """What the badge awarding needs from the store."""

    def fetch_run_hardware_owner(self, run_id: str) -> str | None:
        """The account that owns the machine the run was measured on."""

    def award_badge(self, user_id: str, code: str) -> bool:
        """Grant the badge. Returns True when it was newly granted."""


def award_badges_for_run(
    repository: BadgeRepository, run_id: str, status: str
) -> dict[str, Any] | None:
    """Award what a run's outcome earned. Only a validated run earns one."""
    if status != STATUS_VALIDATED:
        return None
    owner_id = repository.fetch_run_hardware_owner(run_id)
    if not owner_id:
        # The machine belongs to an anonymous contributor, not to an account.
        return None
    granted = repository.award_badge(owner_id, BADGE_FIRST_VERIFIED_RUN)
    return {
        "badge": BADGE_FIRST_VERIFIED_RUN,
        "user_id": owner_id,
        "newly_granted": granted,
    }
