"""Writable row shapes for the session API (S25a: the single run-shape source).

One declaration of what a ``benchmark_run`` / ``benchmark_scenario`` record
carries through ``DatabaseSession.insert_*``. FakeDatabase validates every
inserted record against these models, and the S25a-rt round-trip asserts the
field-set of both backends against ``model_fields`` — so the fake can no longer
accept a record Postgres would reject (or silently truncate). Nullable columns
are required keys with ``None`` allowed: a missing key is a contract error, not
a silent column default. ``extra="forbid"`` turns typos into errors.

Owner principle (direction D2): few hard-required fields; modality-specific
columns stay optional — a new kind of run costs a registry/fixture entry, not
an enum. Video scalars are run columns, never token reuses (AD-1).

Lockstep rule: adding a column means this model, both session implementations,
the migration and the round-trip row updated in the same commit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BenchmarkScenarioRecord(BaseModel):
    """benchmark_scenario row as written through ``insert_scenario``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    scenario_kind: str
    tensor_parallel: int
    # Token dimensions (NULL on video rows) and video dimensions (NULL on LLM
    # rows) coexist per migration 0011; AD-1 forbids reusing either for the
    # other modality.
    prompt_tokens: int | None
    generated_tokens: int | None
    context_tokens: int | None
    batch_size: int | None
    width: int | None
    height: int | None
    frames: int | None
    steps: int | None
    cfg: float | None
    shift: float | None
    seed: int | None


class BenchmarkRunRecord(BaseModel):
    """benchmark_run row as written through ``insert_benchmark_run``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    hardware_submission_id: str
    model_release_id: str
    quantization_profile_id: str
    inference_runtime_id: str
    benchmark_scenario_id: str
    status: str
    client_version: str
    signature: str
    payload_digest: str
    # Video/report columns (migration 0011): NULL on plain LLM runs except
    # source_class, which every run must carry (leaderboard drops empties).
    recipe_id: str | None
    source_class: str | None
    seconds_per_clip: float | None
    it_per_s: float | None
    frames_per_s: float | None
    source_url: str | None
