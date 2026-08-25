"""Tests for the L02 vision-modality probe.

No network: the Ollama HTTP call is faked via an injectable ``http_post``,
mirroring the ``FakeRuntime`` pattern in the sibling probe tests.
"""

import json

from modality_probe import (
    VERDICT_APPROVED,
    VERDICT_UNKNOWN,
    VisionCandidateResult,
    VisionJudgeProbe,
    extract_response_text,
    recognize_verdict,
    select_winner,
)


def _fake_post(payloads):
    """Return an ``http_post`` fake replaying canned JSON payloads in order
    (the last one repeats) and recording every request body."""

    def post(_url, _body):
        post.calls.append(_body)
        payload = payloads[min(len(post.calls), len(payloads)) - 1]
        return json.dumps(payload).encode("utf-8")

    post.calls = []
    return post


def _probe(payloads, model="qwen2.5vl:7b"):
    return VisionJudgeProbe(
        model,
        image_base64="ZmFrZQ==",
        http_post=_fake_post(payloads),
    )


def _result(model, mean, parsable, std=0.0, verdicts=("APROVADO",)):
    return VisionCandidateResult(
        model=model,
        mean_latency_ms=mean,
        std_latency_ms=std,
        parsable=parsable,
        reps=3,
        observed_verdicts=tuple(verdicts),
    )


def test_response_with_verdict_is_parsable():
    probe = _probe([{"response": "Boa hierarquia. Cores consistentes. "
                                "Veredito: APROVADO."}])
    run = probe.judge_once()

    assert run.parsable is True
    assert run.quality_verdict == VERDICT_APPROVED
    assert run.response_size_chars > 0
    assert run.latency_total_ms >= 0.0


def test_response_without_verdict_is_not_parsable():
    probe = _probe([{"response": "A imagem parece aceitavel."}])
    run = probe.judge_once()

    assert run.parsable is False
    assert run.quality_verdict == VERDICT_UNKNOWN


def test_recognize_verdict_is_case_insensitive():
    assert recognize_verdict("revisar") == "REVISAR"
    assert recognize_verdict("termino com aprovado") == "APROVADO"
    assert recognize_verdict("sem veredito aqui") is None


def test_extract_response_text_handles_non_json():
    assert extract_response_text(b"just plain text") == "just plain text"


def test_probe_warmup_plus_reps_and_parsable_aggregation():
    payloads = [
        {"response": "Aquecimento sem veredito."},
        {"response": "Veredito: APROVADO."},
        {"response": "REVISAR."},
        {"response": "APROVADO."},
    ]
    probe = _probe(payloads)
    result = probe.probe(reps=3)

    assert result.reps == 3
    assert result.parsable is True
    assert len(result.observed_verdicts) == 3
    # one discarded warmup + 3 measured runs -> exactly 4 HTTP calls
    assert len(probe._http_post.calls) == 4


def test_winner_prefers_parsable_over_faster():
    fast_unparsable = _result(
        "modelo-a",
        mean=100.0,
        parsable=False,
        verdicts=("desconhecido", "desconhecido", "desconhecido"),
    )
    slow_parsable = _result("modelo-b", mean=500.0, parsable=True)

    winner = select_winner([fast_unparsable, slow_parsable])

    assert winner is not None
    assert winner.model == "modelo-b"


def test_winner_lowest_latency_among_parsable():
    slower = _result("modelo-a", mean=200.0, parsable=True)
    faster = _result("modelo-b", mean=100.0, parsable=True)

    assert select_winner([slower, faster]).model == "modelo-b"


def test_winner_is_none_when_no_candidate_is_parsable():
    results = [
        _result("modelo-a", mean=100.0, parsable=False),
        _result("modelo-b", mean=50.0, parsable=False),
    ]

    assert select_winner(results) is None
