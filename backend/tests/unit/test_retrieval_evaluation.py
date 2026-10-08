import pytest

from app.retrieval.evaluation import evaluate_recall, promotion_decision


def test_boundary_ties_credit_interchangeable_ids_without_hiding_missed_superior_ads() -> None:
    scores = {1: 1.0, 2: 0.8, 3: 0.8, 4: 0.8, 5: 0.2}
    result = evaluate_recall(scores, [1, 2, 3], [1, 3, 4], limit=3)
    assert result.ordinary_recall == pytest.approx(2 / 3)
    assert result.tie_aware_recall == 1
    assert result.missed_superior_count == 0
    missed = evaluate_recall(scores, [1, 2, 3], [2, 3, 4], limit=3)
    assert missed.tie_aware_recall == pytest.approx(2 / 3)
    assert missed.missed_superior_count == 1


def test_empty_inventory_has_unavailable_recall() -> None:
    result = evaluate_recall({}, [], [], limit=500)
    assert result.k == 0
    assert result.ordinary_recall is None
    assert result.tie_aware_recall is None
    assert result.missed_superior_count is None


def test_declared_tolerance_defines_boundary_membership() -> None:
    result = evaluate_recall({1: 1, 2: 0.8, 3: 0.8000004, 4: 0.7}, [1, 3], [1, 2], limit=2)
    assert result.tie_aware_recall == 1
    assert result.boundary_tied_count == 2
    assert result.ordinary_recall == 0.5
    strict = evaluate_recall({1: 1, 2: 0.8, 3: 0.8000004}, [1, 3], [1, 2], limit=2, tolerance=0)
    assert strict.tie_aware_recall == 0.5


@pytest.mark.parametrize("returned", [[1, 1], [99], [1, 2, 3]])
def test_invalid_returned_population_cannot_inflate_recall(returned: list[int]) -> None:
    with pytest.raises(ValueError):
        evaluate_recall({1: 1, 2: 0.5, 3: 0.2}, [1, 2], returned, limit=2)


@pytest.mark.parametrize(
    "hnsw,quality,repetitions,fallback,expected",
    [
        ([9.0, 9.0, 9.0], [0.95, 1.0, 1.0], 3, 0, True),
        ([10.0, 10.0, 10.0], [1.0, 1.0, 1.0], 3, 0, False),
        ([9.0, 9.0, 9.0], [0.94, 1.0, 1.0], 3, 0, False),
        ([9.0, 9.0, 9.0], [1.0, 1.0, 1.0], 1, 0, False),
        ([9.0, 9.0, 9.0], [1.0, 1.0, 1.0], 3, 1, False),
        ([9.0, 9.0, 9.0], [None, None, None], 3, 0, False),
    ],
)
def test_promotion_requires_lower_full_retrieval_p95_and_every_query_meeting_quality(
    hnsw: list[float], quality: list[float | None], repetitions: int, fallback: int, expected: bool
) -> None:
    decision = promotion_decision(
        [10.0, 10.0, 10.0], hnsw, quality, repetitions=repetitions, fallback_count=fallback
    )
    assert decision["eligible"] is expected
    assert decision["applied"] is False
    assert decision["serving_default"] == "flat"


@pytest.mark.parametrize("limit,tolerance", [(0, 1e-6), (501, 1e-6), (1, -1), (1, float("nan"))])
def test_invalid_evaluation_configuration_is_rejected(limit: int, tolerance: float) -> None:
    with pytest.raises(ValueError):
        evaluate_recall({1: 1}, [1], [1], limit=limit, tolerance=tolerance)


def test_incomplete_and_wrong_exact_references_are_rejected() -> None:
    for reference in ([2], [], [1, 1]):
        with pytest.raises(ValueError):
            evaluate_recall({1: 1, 2: 0.1}, reference, [1], limit=1)
