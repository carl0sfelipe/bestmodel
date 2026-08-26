"""S22 tests: localmaxxing import — mapping, priors, idempotency, feed."""

from __future__ import annotations

import pytest

from src.main import create_app
from src.services.import_localmaxxing_claims import (
    BITS_TO_QUANT,
    SOURCE,
    build_claim_record,
    import_cells,
)


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _cell(**overrides):
    cell = {
        "rigKey": "rtx-4090-24gb",
        "modelSlug": "someone-qwen-2-5-coder-7b-gguf",
        "bits": 4,
        "n": 3,
        "tokSOutMedian": 41.2,
        "tokSPrefillMedian": 900.5,
        "ttftMsMedian": 120.0,
        "peakVramGbMedian": 6.2,
        "maxContextTested": 8192,
        "engines": ["llama.cpp"],
    }
    cell.update(overrides)
    return cell


# --- mapping -----------------------------------------------------------------


def test_matching_cell_maps_catalog_and_quant(database):
    from src.services.import_localmaxxing_claims import CatalogIndex

    index = CatalogIndex(database)
    record, skip = build_claim_record(index, _cell())
    assert skip is None and record is not None
    assert record["model_release_id"] == "model-qwen25-coder-7b"
    assert record["quantization_profile_id"] == "q-gguf-q4-k-m"
    assert record["gpu_model_id"] == "gpu-rtx-4090"
    assert record["claimant_id"] is None
    assert record["source"] == SOURCE
    assert record["external_ref"] == "localmaxxing:rtx-4090-24gb:someone-qwen-2-5-coder-7b-gguf:4"
    assert record["claimed_metrics"]["decode_tok_s"] == 41.2
    assert record["claimed_metrics"]["peak_vram_mib"] == 6349
    assert "owner-approved" in record["note"]


def test_gpu_specificity_prefers_exact_suffix(database):
    """rtx-3060 must not match 3060 Ti; the shortest matching suffix wins."""
    from src.services.import_localmaxxing_claims import CatalogIndex

    index = CatalogIndex(database)
    assert index.match_gpu("rtx-3060-12gb") == "gpu-rtx-3060"
    assert index.match_gpu("5060-ti-16gb") is None  # not in the 23-GPU catalog
    assert index.match_gpu("m4-16gb") is None  # Apple rigs stay unmapped


def test_multigpu_missing_median_and_unknown_model_skip(database):
    from src.services.import_localmaxxing_claims import CatalogIndex

    index = CatalogIndex(database)
    assert build_claim_record(index, _cell(rigKey="rtx-3090-24gb-x2"))[1] == "multigpu-v1"
    assert build_claim_record(index, _cell(tokSOutMedian=None))[1] == "nometrics"
    assert build_claim_record(index, _cell(modelSlug="aeon-7-glm-5-2-504b"))[1] == "nomodel"


# --- import + idempotency ------------------------------------------------------


def test_apply_imports_and_is_idempotent(database):
    stats = import_cells(database, [_cell(), _cell(rigKey="rtx-3090-24gb")], dry_run=False)
    assert stats["imported"] == 2 and stats["existing"] == 0

    again = import_cells(database, [_cell(), _cell(rigKey="rtx-3090-24gb")], dry_run=False)
    assert again["imported"] == 0 and again["existing"] == 2
    assert len(database._claims) == 2

    stored = database.find_run_claim_by_external_ref(
        "localmaxxing:rtx-4090-24gb:someone-qwen-2-5-coder-7b-gguf:4"
    )
    assert stored["status"] == "open"
    prior = stored["prior_snapshot"]
    assert prior["pool"]["basis"] == "reported"
    assert prior["pool"]["run_count"] == 3
    assert prior["pool"]["p50_decode_tok_s"] == 41.2
    # roofline prior resolves because model+quant+gpu all mapped
    assert prior["roofline"] is not None


def test_dry_run_never_writes(database):
    stats = import_cells(database, [_cell()], dry_run=True)
    assert stats["imported"] == 1
    assert database._claims == []


# --- feed + votes + cards on imported claims ----------------------------------


def test_imported_claims_surface_everywhere(client, database):
    import_cells(database, [_cell()], dry_run=False)

    listing = client.get("/v1/claims?sort=recent").json()
    imported = next(c for c in listing if c.get("source") == "localmaxxing")
    assert imported["claimant_handle"] == "localmaxxing pool"

    detail = client.get(f"/v1/claims/{imported['id']}").json()
    assert detail["handle"] == "localmaxxing pool"

    card = client.get(f"/v1/cards/claims/{imported['id']}.svg").text
    assert "@localmaxxing pool" in card


def test_community_can_vote_on_imported_claims(client, database, monkeypatch):
    from conftest import make_passkey_session

    import_cells(database, [_cell()], dry_run=False)
    token = make_passkey_session(client, database, monkeypatch, "grace")
    claim = next(c for c in client.get("/v1/claims").json() if c.get("source") == "localmaxxing")

    # claimant is NULL → no self-vote guard applies; community judges freely
    vote = client.post(
        f"/v1/claims/{claim['id']}/votes",
        json={"verdict": "plausible"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vote.status_code == 200
    assert vote.json()["tally"]["plausible_count"] == 1

    # retraction stays impossible for ownerless claims
    retract = client.post(
        f"/v1/claims/{claim['id']}/retract", headers={"Authorization": f"Bearer {token}"}
    )
    assert retract.status_code == 403
