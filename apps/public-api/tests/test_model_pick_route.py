"""Route tests for GET /v1/pick (S49, contract model-pick-v1)."""

from __future__ import annotations

import json

import pytest

PICK_FIELDS = {"model_id", "hf_repo", "quant", "bits", "runtime", "vram_peak_gib", "perf", "quality", "confidence", "evidence", "perf_concurrency_8"}
CONFIDENCES = {"measured", "reported", "extrapolated", "formula", "no data yet"}


def _cell(slug, tok_s, peak, n=3, rig="rtx-3090-24gb", c8=None):
    extra = {} if c8 is None else {"tokSOutC8Median": c8[0], "peakVramGbC8Median": c8[1]}
    return extra | {"rigKey": rig, "modelSlug": slug, "bits": 4, "n": n, "tokSOutMedian": tok_s,
            "tokSPrefillMedian": None, "ttftMsMedian": None, "peakVramGbMedian": peak,
            "maxContextTested": 8192, "engines": ["llama.cpp"]}


def _model(slug, category="chat", source_class="community_reported", score=None):
    model = {"slug": slug, "hfId": f"org/{slug}", "category": category, "sourceClass": source_class}
    if score is not None:
        model["evalScore"] = {"score": score, "count": 5}
    return model


@pytest.fixture()
def snapshot(tmp_path, monkeypatch):
    cells = [
        _cell("fast-small", 120.0, 6.0, n=40, c8=(410.0, 9.5)),
        _cell("slow-big", 30.0, 21.0, n=1, c8=(150.0, 26.0)),
        _cell("tiny-fast", 700.0, 2.0),
        _cell("c8-no-peak", 50.0, 3.0, c8=(200.0, None)),
        _cell("too-big", 200.0, 30.0),
        _cell("no-peak", 300.0, None),
        _cell("other-rig", 500.0, 4.0, rig="rtx-4090-24gb"),
        _cell("image-model", 999.0, 4.0),
        _cell("signed-unknown", 400.0, 4.0),
    ]
    models = [_model("fast-small", score=0.6), _model("tiny-fast"), _model("c8-no-peak"), _model("slow-big", score=0.9), _model("too-big"), _model("no-peak"),
              _model("other-rig"), _model("image-model", category="image"),
              _model("signed-unknown", source_class="something_new")]
    (tmp_path / "pool.json").write_text(json.dumps({"snapshotAt": "2026-09-18T00:00:00Z", "cells": cells}))
    (tmp_path / "models.json").write_text(json.dumps({"models": models}))
    (tmp_path / "hardware.json").write_text(json.dumps({"rigs": [{"key": "rtx-3090-24gb"}, {"key": "rtx-4090-24gb"}]}))
    monkeypatch.setenv("BESTMODEL_POOL_SNAPSHOT_DIR", str(tmp_path))


def _pick(client, **params):
    query = {"intent": "chat", "vram_gib": 24, "gpu": "rtx-3090-24gb"} | params
    return client.get("/v1/pick", params=query)


def test_chat_picks_rank_by_confidence_then_quality_then_speed(client, snapshot):
    body = _pick(client).json()
    assert body["contract"] == "model-pick-v1"
    ids = [pick["model_id"] for pick in body["picks"]]
    # A fast unscored model never outranks a scored one.
    assert ids == ["slow-big", "fast-small", "tiny-fast", "c8-no-peak", "signed-unknown"]
    for pick in body["picks"]:
        assert set(pick) == PICK_FIELDS
        assert pick["vram_peak_gib"] <= 24
        assert pick["confidence"] in CONFIDENCES


def test_community_reports_are_never_measured(client, snapshot):
    picks = _pick(client).json()["picks"]
    assert "measured" not in {pick["confidence"] for pick in picks}
    assert {p["model_id"]: p["confidence"] for p in picks}["fast-small"] == "reported"


def test_unrecognized_source_class_is_downgraded(client, snapshot):
    picks = {p["model_id"]: p for p in _pick(client).json()["picks"]}
    assert picks["signed-unknown"]["confidence"] == "no data yet"


def test_vram_budget_filters_rows(client, snapshot):
    ids = [p["model_id"] for p in _pick(client, vram_gib=10).json()["picks"]]
    assert ids == ["fast-small", "tiny-fast", "c8-no-peak", "signed-unknown"]


@pytest.mark.parametrize("intent", ["image.generate", "vision", "audio"])
def test_intent_without_cells_says_no_data_yet(client, snapshot, intent):
    body = _pick(client, intent=intent).json()
    assert body["picks"] == []
    assert body["confidence_floor"] == "no data yet"


def test_unknown_intent_is_400_with_valid_list(client, snapshot):
    response = _pick(client, intent="dance")
    assert response.status_code == 400
    assert "image.generate" in response.json()["detail"]


def test_unknown_gpu_is_400(client, snapshot):
    assert _pick(client, gpu="gpu-rtx-3090").status_code == 400


def test_non_positive_vram_is_422(client, snapshot):
    assert _pick(client, vram_gib=0).status_code == 422


def test_published_snapshot_answers_every_intent(client):
    # Real snapshot shipped in the API image: every v1 intent answers 200.
    for intent in ("chat", "image.generate", "vision", "audio"):
        response = _pick(client, intent=intent)
        assert response.status_code == 200
        assert all(p["confidence"] != "measured" for p in response.json()["picks"])


def test_concurrency_8_only_where_measured_and_fitting(client, snapshot):
    picks = {p["model_id"]: p["perf_concurrency_8"] for p in _pick(client).json()["picks"]}
    assert picks["fast-small"] == {"metric": "decode_tok_s", "value": 410.0, "concurrency": 8,
                                   "vram_peak_gib": 9.5, "confidence": "reported"}
    # measured at 8 slots, but its 8-slot peak (26 GiB) exceeds the 24 GiB budget
    assert picks["slow-big"]["value"] is None and picks["slow-big"]["confidence"] == "no data yet"
    # never measured at 8 slots: no number is invented
    assert picks["tiny-fast"]["value"] is None and picks["tiny-fast"]["confidence"] == "no data yet"
    # 8-slot speed without the 8-slot peak: fit unproven, not offered
    assert picks["c8-no-peak"]["value"] is None
    assert all(p["concurrency"] == 8 for p in picks.values())


def test_concurrency_8_never_promotes_confidence(client, snapshot):
    for pick in _pick(client).json()["picks"]:
        c8 = pick["perf_concurrency_8"]["confidence"]
        assert CONFIDENCES and (c8 == "no data yet" or c8 == pick["confidence"])
