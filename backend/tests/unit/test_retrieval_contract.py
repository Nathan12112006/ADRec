from decimal import Decimal
from uuid import UUID

import pytest

from app.retrieval.contracts import RetrievalCandidate, RetrievalResult, RetrievalUser


def candidate(ad_id: int, *, similarity: float | None = 1.0) -> RetrievalCandidate:
    return RetrievalCandidate(
        id=ad_id,
        dataset_id=UUID("00000000-0000-0000-0000-000000000001"),
        advertiser_id=10,
        title="Synthetic offer",
        description="Fictional advertisement",
        target_url="https://example.test/ad",
        category="technology",
        interests=("technology",),
        bid=Decimal("1.25"),
        similarity=similarity,
    )


def test_exact_result_reports_current_candidates_and_retrieval_diagnostics() -> None:
    result = RetrievalResult(
        candidates=(candidate(3),),
        mode="exact",
        index_version="snapshot-1",
        requested_count=500,
        elapsed_ms=1.5,
    )
    assert result.returned_count == 1
    assert result.model_dump()["returned_count"] == 1
    assert result.candidates[0].bid == Decimal("1.25")
    assert result.candidates[0].similarity == 1
    assert result.vocabulary_version == "topics-v1"
    assert result.vector_version == "binary-cosine-v1"
    assert result.fallback_reason is None


@pytest.mark.parametrize("limit", [0, -1, 501, 1.5, True])
def test_requested_candidate_limit_is_a_positive_bounded_integer(limit: object) -> None:
    with pytest.raises(ValueError):
        RetrievalResult.model_validate(
            {
                "candidates": (),
                "mode": "exact",
                "index_version": "snapshot-1",
                "requested_count": limit,
                "elapsed_ms": 0,
            }
        )


@pytest.mark.parametrize("ids,limit", [((1, 1), 2), ((1, 2), 1), ((2, 1), 2)])
def test_result_rejects_duplicate_excess_or_inconsistently_ordered_candidates(
    ids: tuple[int, ...],
    limit: int,
) -> None:
    with pytest.raises(ValueError):
        RetrievalResult(
            candidates=tuple(candidate(ad_id) for ad_id in ids),
            mode="exact",
            index_version="snapshot-1",
            requested_count=limit,
            elapsed_ms=0,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 0),
        ("advertiser_id", -1),
        ("bid", "-0.01"),
        ("bid", "NaN"),
        ("similarity", float("nan")),
        ("similarity", float("inf")),
        ("similarity", -0.1),
        ("similarity", 1.1),
        ("active", False),
        ("advertiser_active", False),
        ("category", "unknown"),
        ("interests", ("unknown",)),
    ],
)
def test_invalid_or_ineligible_current_metadata_is_not_a_candidate(
    field: str, value: object
) -> None:
    payload = candidate(1).model_dump()
    payload[field] = value
    with pytest.raises(ValueError):
        RetrievalCandidate.model_validate(payload)


@pytest.mark.parametrize("ids,similarity", [((2, 1), None), ((1, 2), 1.0)])
def test_nonpersonalized_fallback_requires_bid_id_order_and_no_cosine_score(
    ids: tuple[int, ...],
    similarity: float | None,
) -> None:
    with pytest.raises(ValueError):
        RetrievalResult(
            candidates=tuple(candidate(ad_id, similarity=similarity) for ad_id in ids),
            mode="nonpersonalized",
            fallback_reason="empty_interests",
            requested_count=2,
            elapsed_ms=0,
        )


@pytest.mark.parametrize(
    "mode,index,reason,elapsed",
    [
        ("exact", None, None, 0),
        ("hnsw", "", None, 0),
        ("exact", "snapshot-1", "stale_index", 0),
        ("exact_fallback", None, None, 0),
        ("exact_fallback", None, "empty_interests", 0),
        ("exact_fallback", "snapshot-1", "stale_index", 0),
        ("nonpersonalized", None, None, 0),
        ("nonpersonalized", None, "missing_index", 0),
        ("nonpersonalized", "snapshot-1", "empty_interests", 0),
        ("exact", "snapshot-1", None, -1),
        ("exact", "snapshot-1", None, float("inf")),
        ("exact", "snapshot-1", None, float("nan")),
    ],
)
def test_diagnostics_cannot_mislabel_fallback_or_invalid_latency(
    mode: str,
    index: str | None,
    reason: str | None,
    elapsed: float,
) -> None:
    with pytest.raises(ValueError):
        RetrievalResult.model_validate(
            {
                "candidates": (),
                "mode": mode,
                "index_version": index,
                "fallback_reason": reason,
                "requested_count": 500,
                "elapsed_ms": elapsed,
            }
        )


def test_nonpersonalized_result_accepts_bid_order_with_null_similarity() -> None:
    higher_bid = RetrievalCandidate.model_validate(
        {**candidate(2, similarity=None).model_dump(), "bid": "2.50"}
    )
    result = RetrievalResult(
        candidates=(higher_bid, candidate(1, similarity=None), candidate(3, similarity=None)),
        mode="nonpersonalized",
        requested_count=500,
        elapsed_ms=0,
        fallback_reason="empty_interests",
    )
    assert [ad.id for ad in result.candidates] == [2, 1, 3]
    assert result.returned_count == 3
    assert all(ad.similarity is None for ad in result.candidates)


@pytest.mark.parametrize(
    "reason",
    [
        "missing_index",
        "stale_index",
        "corrupt_index",
        "incompatible_index",
        "insufficient_candidates",
    ],
)
def test_current_inventory_exact_fallback_retains_its_reason(reason: str) -> None:
    result = RetrievalResult.model_validate(
        {
            "candidates": [candidate(2, similarity=0.8), candidate(1, similarity=0.5)],
            "mode": "exact_fallback",
            "requested_count": 500,
            "elapsed_ms": 2.5,
            "fallback_reason": reason,
        }
    )
    assert result.fallback_reason == reason
    assert result.index_version is None
    assert [ad.id for ad in result.candidates] == [2, 1]


def test_empty_inventory_is_an_explicit_zero_count_not_a_fake_candidate() -> None:
    result = RetrievalResult(
        candidates=(), mode="exact", index_version="snapshot-1", requested_count=1, elapsed_ms=0
    )
    assert result.returned_count == 0


def test_empty_interest_user_remains_valid_for_nonpersonalized_retrieval() -> None:
    user = RetrievalUser(id=1, dataset_id=UUID(int=1), interests=())
    assert user.interests == ()


@pytest.mark.parametrize("field,value", [("id", 0), ("interests", ("unknown",))])
def test_invalid_retrieval_user_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        RetrievalUser.model_validate(
            {"id": 1, "dataset_id": UUID(int=1), "interests": (), field: value}
        )
