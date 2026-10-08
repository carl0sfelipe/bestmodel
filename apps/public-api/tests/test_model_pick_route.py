"""Route tests for GET /v1/pick (S49, contract model-pick-v1)."""

from __future__ import annotations

import json

import pytest

PICK_FIELDS = {"model_id", "hf_repo", "quant", "bits", "runtime", "vram_peak_gib", "perf", "quality", "confidence", "evidence"}
CONFIDENCES = {"measured", "reported", "extrapolated", "formula", "no data yet"}


def _cell(slug, tok_s, peak, n=3, rig="rtx-3090-24gb"):
    return {"rigKey": rig, "modelSlug": slug, "bits": 4, "n": n, "tokSOutMedian": tok_s,
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
        _cell("fast-small", 120.0, 6.0, n=40),
        _cell("slow-big", 30.0, 21.0, n=1),
        _cell("tiny-fast", 700.0, 2.0),
        _cell("too-big", 200.0, 30.0),
        _cell("no-peak", 300.0, None),
        _cell("other-rig", 500.0, 4.0, rig="rtx-4090-24gb"),
        _cell("image-model", 999.0, 4.0),
        _cell("signed-unknown", 400.0, 4.0),
    ]
    models = [_model("fast-small", score=0.6), _model("tiny-fast"), _model("slow-big", score=0.9), _model("too-big"), _model("no-peak"),
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
    assert ids == ["slow-big", "fast-small", "tiny-fast", "signed-unknown"]
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
    assert ids == ["fast-small", "tiny-fast", "signed-unknown"]


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
