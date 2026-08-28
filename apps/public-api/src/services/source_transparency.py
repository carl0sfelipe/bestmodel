"""Public source transparency data (Story 5.3, FR-3 / NFR-4).

Single source of truth for what each ``source_class`` means, how it is
produced, whether it reaches the leaderboard, and how an outsider can audit
it. The weights mirror ``source_weight`` in ``cli/canirunit/src/lib.rs`` —
keep the two in sync when tuning confidence (Story 2.3 contract).
"""

from __future__ import annotations

LEADERBOARD_RULE = (
    "A leaderboard reads only benchmark_run rows with status='validated' AND "
    "source_class IS NOT NULL; a cell without a declared source class never renders."
)

SOURCE_CLASSES: list[dict] = [
    {
        "source_class": "measured_signed",
        "confidence_base_weight": 0.9,
        "what_it_is": (
            "Benchmark run by the benchmark-probe CLI on real hardware, signed with "
            "the submitter's local Ed25519 key."
        ),
        "how_it_is_produced": (
            "The CLI detects the hardware, runs the standardized scenario, "
            "canonicalizes the report (sorted-key compact JSON), computes "
            "sha256(payload), signs the digest, and uploads report+digest+signature+artifacts."
        ),
        "enters_leaderboard": "directly (status becomes validated after intake checks)",
        "how_to_audit": [
            "Recompute the digest: canonicalize the report JSON with sort_keys=True and "
            "separators=(',', ':'), then sha256 it — it must equal the stored payload_digest.",
            "Verify the Ed25519 signature of payload_digest with the project's trusted "
            "public key (verify offline with openssl or the 'cryptography' package).",
            "Each artifact row stores the sha256 of its uploaded bytes — re-hash the "
            "artifact and compare (benchmark_artifact.sha256_digest).",
        ],
    },
    {
        "source_class": "reported",
        "confidence_base_weight": 0.6,
        "what_it_is": (
            "A number measured outside the signed probe (e.g. another benchmark tool) "
            "and reported through the authenticated community endpoint."
        ),
        "how_it_is_produced": (
            "POST /v1/submissions/reported with a contributor bearer token; quota-"
            "limited per source IP; stored with status='submitted' and the literal "
            "signature 'reported' (no Ed25519 claim is made)."
        ),
        "enters_leaderboard": (
            "only after human review flips status to validated — it never enters "
            "directly, and it always keeps the reported badge"
        ),
        "how_to_audit": [
            "payload_digest is sha256 of the canonical request body (sorted keys, "
            "compact separators) — it proves what was submitted, not that it is true.",
            "The per-IP submission log (reported_submission_log) records contributor, "
            "run and IP for every accepted report.",
            "Treat the number as a claim by the account that owns it.",
        ],
    },
    {
        "source_class": "harvested",
        "confidence_base_weight": 0.4,
        "what_it_is": (
            "A measurement extracted by a deterministic harvester from a public "
            "source (model cards, workflow templates)."
        ),
        "how_it_is_produced": (
            "Harvesters run offline against fetched sources, stage cells as JSONL "
            "(status=unverified, never production), and a human review decision "
            "(commitable decisions file) promotes them with deterministic uuid5 ids."
        ),
        "enters_leaderboard": "only via the review queue promotion (keeps the harvested badge)",
        "how_to_audit": [
            "Every cell carries source_url — open the exact source it came from.",
            "source_sha256 is the hash of the source bytes at harvest time; re-fetch "
            "and re-hash to detect mutations (a changed hash is rejected, not merged).",
            "Staging JSONL is append-only and immutable under review; the approval "
            "lives in a separate decisions file that is itself commitable.",
        ],
    },
    {
        "source_class": "derived",
        "confidence_base_weight": 0.4,
        "what_it_is": (
            "A roofline-based estimate computed by the project (never a measurement), "
            "including cross-hardware transfers from an anchored measured cell."
        ),
        "how_it_is_produced": (
            "packages/roofline-kernel estimate functions from published hardware specs; "
            "cross-hardware suggestions scale the anchor's measured value by the "
            "effective-throughput ratio eff(anchor)/eff(target)."
        ),
        "enters_leaderboard": (
            "derived cells may appear with the derived badge when published; the "
            "suggest CLI always labels them 'derived, not measured on your hardware'"
        ),
        "how_to_audit": [
            "source_url points at the estimator version "
            "(e.g. roofline:estimate_diffusion_step#v1) — rerun the estimator with the "
            "published specs and parameters to reproduce the number.",
            "The attention calibration constant is DECLARED, not fitted; it is "
            "documented in the estimator source.",
            "A derived value must never claim measured_signed; that swap is the "
            "project's hard honesty line.",
        ],
    },
]


def source_transparency() -> dict:
    return {
        "principle": (
            "Every cell declares where its number came from (source_class) and the "
            "confidence weight follows that declaration — a measurement, a community "
            "report, a harvest and an estimate are never presented alike."
        ),
        "leaderboard_rule": LEADERBOARD_RULE,
        "classes": SOURCE_CLASSES,
        "confidence_note": (
            "confidence_base_weight is the class factor of the public confidence "
            "formula (see cli/canirunit src/lib.rs source_weight); the final score "
            "also combines run count, freshness, variance and match tier."
        ),
    }
