from filter_feasible_models import (
    filter_feasible_models,
    is_feasible,
    mark_feasibility,
    usable_memory_mib,
)


def make_candidate(name, peak, capacity):
    return {"name": name, "peak_vram_mib": peak, "vram_capacity_mib": capacity}


def test_usable_memory_applies_safety_margin():
    assert usable_memory_mib(24576) == 24576 * 0.95


def test_feasibility_boundary_follows_point_nine_five_rule():
    capacity = 24576
    assert is_feasible(capacity * 0.95, capacity)
    assert not is_feasible(capacity * 0.95 + 1, capacity)


def test_unknown_capacity_passes_through():
    assert is_feasible(99999.0, None)


def test_mark_feasibility_annotates_each_candidate():
    candidates = [
        make_candidate("fits", 20000, 24576),
        make_candidate("overflows", 24000, 24576),
    ]
    marked = mark_feasibility(candidates)
    assert marked[0]["feasible"] is True
    assert marked[1]["feasible"] is False


def test_filter_hides_infeasible_candidates():
    candidates = mark_feasibility(
        [make_candidate("fits", 20000, 24576), make_candidate("overflows", 24000, 24576)]
    )
    remaining = filter_feasible_models(candidates)
    assert [c["name"] for c in remaining] == ["fits"]
