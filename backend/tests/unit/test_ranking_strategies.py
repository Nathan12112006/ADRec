from decimal import Decimal, Inexact, localcontext
from typing import Any

import numpy as np
import pytest

from app.ctr.serving import CTRModel, CTRUnavailable
from app.ranking.strategies import InterestOverlap


class Estimator:
    """External estimator fixture exercised through the real CTR adapter."""

    classes_ = np.asarray([0, 1])

    def __init__(self, probabilities: list[float]) -> None:
        self.probabilities = probabilities
        self.batches: list[Any] = []

    def predict_proba(self, matrix: Any) -> Any:
        self.batches.append(matrix.tolist())
        return np.asarray([[1 - p, p] for p in self.probabilities])


def test_v1_orders_distinct_overlap_then_exact_bid_then_id_without_a_model() -> None:
    result = InterestOverlap().rank(
        {"interests": ["music", "music", "gaming"]},
        [
            {"id": 4, "interests": ["music", "music"], "bid": "99"},
            {"id": 3, "interests": ["music", "gaming"], "bid": "1.0002"},
            {"id": 2, "interests": ["music", "gaming"], "bid": "1.0002"},
            {"id": 1, "interests": ["music", "gaming"], "bid": "1.0001"},
        ],
    )
    assert [ad.ad_id for ad in result.candidates] == [2, 3, 1, 4]
    assert [ad.score for ad in result.candidates] == [2, 2, 2, 1]
    assert result.candidates[0].bid == Decimal("1.0002")
    assert result.strategy == "interest-overlap"
    assert result.strategy_version == "baseline-v1"
    assert result.score_meaning == "distinct_shared_interest_count"
    assert (
        result.model_id is None and result.model_version is None and result.feature_version is None
    )
    assert all(ad.predicted_ctr is None for ad in result.candidates)


def test_v2_uses_one_aligned_batch_and_expected_value_instead_of_bid_or_ctr_alone() -> None:
    from app.ranking.strategies import ExpectedValue

    estimator = Estimator([0.1, 0.02, 0.2])
    result = ExpectedValue(CTRModel(estimator, "fixture-model")).rank(
        {"interests": ["music"]},
        [
            {"id": 9, "interests": ["music"], "category": "music", "bid": "1.00"},
            {"id": 4, "interests": [], "category": "cars", "bid": "3.00"},
            {"id": 3, "interests": [], "category": "gaming", "bid": "0.25"},
        ],
    )
    assert [(ad.ad_id, ad.score, ad.predicted_ctr) for ad in result.candidates] == [
        (9, Decimal("0.100"), 0.1),
        (4, Decimal("0.0600"), 0.02),
        (3, Decimal("0.050"), 0.2),
    ]
    assert len(estimator.batches) == 1
    assert [row[2] for row in estimator.batches[0]] == ["music", "cars", "gaming"]
    assert result.strategy == "expected-value"
    assert result.strategy_version == "expected-value-v1"
    assert result.score_meaning == "expected_simulated_dollars_per_impression"
    assert result.model_id == "fixture-model"
    assert result.model_version == "ctr-logistic-v1"
    assert result.feature_version == "ctr-features-v1"


def test_exact_scores_and_order_do_not_depend_on_decimal_context_or_display_rounding() -> None:
    from app.ranking.strategies import ExpectedValue

    ads = [{"id": 1, "bid": "1.00000001"}, {"id": 2, "bid": "1.00000002"}]
    with localcontext() as context:
        context.prec = 4
        context.traps[Inexact] = True
        v1 = InterestOverlap().rank({}, ads)
        v2 = ExpectedValue(CTRModel(Estimator([0.1, 0.1]), "fixture")).rank({}, ads)
    assert [ad.ad_id for ad in v1.candidates] == [2, 1]
    assert [ad.ad_id for ad in v2.candidates] == [2, 1]
    assert v2.candidates[0].score == Decimal("0.100000002")
    assert '"score":"0.100000002"' in v2.model_dump_json()


def test_empty_rankings_need_no_model_or_inference_and_nonempty_v2_fails_unavailable() -> None:
    from app.ranking.strategies import ExpectedValue, RankingStrategy

    strategies: list[RankingStrategy] = [InterestOverlap(), ExpectedValue(CTRModel.unavailable())]
    for strategy in strategies:
        result = strategy.rank({}, [])
        assert result.candidates == ()
        assert (
            result.model_id is None
            and result.model_version is None
            and result.feature_version is None
        )
    with pytest.raises(CTRUnavailable) as failure:
        strategies[1].rank({}, [{"id": 1, "bid": "0"}])
    assert failure.value.status_code == 503 and failure.value.code == "ctr_unavailable"


def test_v2_equal_expected_values_use_overlap_then_bid_then_ascending_id() -> None:
    from app.ranking.strategies import ExpectedValue

    result = ExpectedValue(CTRModel(Estimator([0.125, 0.5, 0.5, 0.25]), "fixture")).rank(
        {"interests": ["music"]},
        [
            {"id": 4, "bid": "4", "interests": []},
            {"id": 3, "bid": "1", "interests": ["music"]},
            {"id": 2, "bid": "1", "interests": ["music"]},
            {"id": 1, "bid": "2", "interests": ["music"]},
        ],
    )
    assert [ad.ad_id for ad in result.candidates] == [1, 2, 3, 4]
    assert all(ad.score == Decimal("0.5") for ad in result.candidates)


@pytest.mark.parametrize("v2", [False, True])
@pytest.mark.parametrize("interests", [[], ["music"]])
def test_zero_bids_remain_in_the_ordered_result_even_when_every_score_is_zero(
    v2: bool, interests: list[str]
) -> None:
    from app.ranking.strategies import ExpectedValue

    strategy = (
        ExpectedValue(CTRModel(Estimator([0.0, 1.0]), "fixture")) if v2 else InterestOverlap()
    )
    result = strategy.rank(
        {"interests": interests},
        [{"id": 2, "bid": "0", "interests": ["music"]}, {"id": 1, "bid": "0"}],
    )
    assert [ad.ad_id for ad in result.candidates] == ([2, 1] if interests else [1, 2])
    if v2 or not interests:
        assert all(ad.score == 0 for ad in result.candidates)


@pytest.mark.parametrize("v2", [False, True])
def test_no_interest_user_keeps_bid_then_id_ties_and_zero_bid_eligibility(v2: bool) -> None:
    from app.ranking.strategies import ExpectedValue

    strategy = (
        ExpectedValue(CTRModel(Estimator([0.1, 0.1, 0.1]), "fixture")) if v2 else InterestOverlap()
    )
    result = strategy.rank(
        {}, [{"id": 3, "bid": "0"}, {"id": 2, "bid": "1"}, {"id": 1, "bid": "1"}]
    )
    assert [ad.ad_id for ad in result.candidates] == [1, 2, 3]
    assert all(ad.shared_interest_count == 0 for ad in result.candidates)


@pytest.mark.parametrize("v2", [False, True])
@pytest.mark.parametrize("bid", ["-1", "NaN", "sNaN", "Infinity", "-Infinity", "bad"])
def test_invalid_bids_fail_as_data_errors_without_becoming_zero_or_triggering_inference(
    v2: bool, bid: str
) -> None:
    from app.ranking.strategies import ExpectedValue

    estimator = Estimator([0.1])
    strategy = ExpectedValue(CTRModel(estimator, "fixture")) if v2 else InterestOverlap()
    with pytest.raises(ValueError):
        strategy.rank({}, [{"id": 1, "bid": bid}])
    assert estimator.batches == []


@pytest.mark.parametrize("probabilities", [[float("nan")], [float("inf")], [-0.1], [1.1], []])
def test_v2_invalid_estimator_probabilities_or_count_raise_typed_unavailable(
    probabilities: list[float],
) -> None:
    from app.ranking.strategies import ExpectedValue

    with pytest.raises(CTRUnavailable):
        ExpectedValue(CTRModel(Estimator(probabilities), "fixture")).rank(
            {}, [{"id": 1, "bid": "1"}]
        )


@pytest.mark.parametrize("v2", [False, True])
def test_duplicate_candidate_ids_are_rejected_before_ranking_or_inference(v2: bool) -> None:
    from app.ranking.strategies import ExpectedValue

    estimator = Estimator([0.1, 0.2])
    strategy = ExpectedValue(CTRModel(estimator, "fixture")) if v2 else InterestOverlap()
    with pytest.raises(ValueError, match="distinct"):
        strategy.rank({}, [{"id": 1, "bid": "1"}, {"id": 1, "bid": "2"}])
    assert estimator.batches == []
