"""Story 5.3 — public source transparency endpoint."""

from __future__ import annotations

EXPECTED_CLASSES = {
    "measured_signed": 0.9,
    "reported": 0.6,
    "harvested": 0.4,
    "derived": 0.4,
}


def test_transparency_lists_exactly_the_four_source_classes(client):
    response = client.get("/v1/transparency/sources")
    assert response.status_code == 200
    body = response.json()
    classes = {entry["source_class"]: entry for entry in body["classes"]}
    assert set(classes) == set(EXPECTED_CLASSES)


def test_transparency_weights_match_the_confidence_implementation(client):
    body = client.get("/v1/transparency/sources").json()
    classes = {entry["source_class"]: entry for entry in body["classes"]}
    for source_class, weight in EXPECTED_CLASSES.items():
        assert classes[source_class]["confidence_base_weight"] == weight


def test_transparency_every_class_explains_production_and_audit(client):
    body = client.get("/v1/transparency/sources").json()
    for entry in body["classes"]:
        assert entry["what_it_is"].strip()
        assert entry["how_it_is_produced"].strip()
        assert entry["enters_leaderboard"].strip()
        assert len(entry["how_to_audit"]) >= 1
        assert all(isinstance(step, str) and step.strip() for step in entry["how_to_audit"])


def test_transparency_states_leaderboard_rule_and_honesty_lines(client):
    body = client.get("/v1/transparency/sources").json()
    assert "validated" in body["leaderboard_rule"]
    reported = next(c for c in body["classes"] if c["source_class"] == "reported")
    assert "human review" in reported["enters_leaderboard"]
    derived = next(c for c in body["classes"] if c["source_class"] == "derived")
    assert any("never claim measured_signed" in step for step in derived["how_to_audit"])
    harvested = next(c for c in body["classes"] if c["source_class"] == "harvested")
    assert any("source_sha256" in step for step in harvested["how_to_audit"])
    signed = next(c for c in body["classes"] if c["source_class"] == "measured_signed")
    assert any("payload_digest" in step for step in signed["how_to_audit"])
