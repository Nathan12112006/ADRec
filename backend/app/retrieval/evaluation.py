"""Tie-aware retrieval quality against a frozen exact score population."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil, isfinite
from typing import Any


@dataclass(frozen=True)
class RecallEvaluation:
    ordinary_recall: float | None
    tie_aware_recall: float | None
    missed_superior_count: int | None
    boundary_score: float | None
    superior_count: int
    boundary_tied_count: int
    returned_count: int
    k: int


def evaluate_recall(
    scores: Mapping[int, float],
    reference_ids: Sequence[int],
    returned_ids: Sequence[int],
    *,
    limit: int,
    tolerance: float = 1e-6,
) -> RecallEvaluation:
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if not isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    if any(not isfinite(score) or not 0 <= score <= 1 for score in scores.values()):
        raise ValueError("reference scores must be finite cosine similarities")
    k = min(limit, len(scores))
    for ids in (reference_ids, returned_ids):
        if len(set(ids)) != len(ids) or not set(ids) <= scores.keys() or len(ids) > k:
            raise ValueError("IDs must be distinct eligible members within k")
    if len(reference_ids) != k:
        raise ValueError("exact reference must contain k members")
    if k == 0:
        return RecallEvaluation(None, None, None, None, 0, 0, 0, 0)
    boundary = sorted(scores.values(), reverse=True)[k - 1]
    superior = {ad_id for ad_id, score in scores.items() if score > boundary + tolerance}
    tied = {ad_id for ad_id, score in scores.items() if abs(score - boundary) <= tolerance}
    if not superior <= set(reference_ids) or not set(reference_ids) <= superior | tied:
        raise ValueError("reference IDs must describe an exact top-k set")
    returned = set(returned_ids)
    return RecallEvaluation(
        ordinary_recall=len(set(reference_ids) & returned) / k,
        tie_aware_recall=(len(superior & returned) + min(len(tied & returned), k - len(superior)))
        / k,
        missed_superior_count=len(superior - returned),
        boundary_score=boundary,
        superior_count=len(superior),
        boundary_tied_count=len(tied),
        returned_count=len(returned),
        k=k,
    )


def promotion_decision(
    flat_retrieval_ms: Sequence[float],
    hnsw_retrieval_ms: Sequence[float],
    tie_aware_recalls: Sequence[float | None],
    *,
    repetitions: int,
    fallback_count: int,
) -> dict[str, Any]:
    """Conservative eligibility only; never mutates production configuration."""
    if not len(flat_retrieval_ms) == len(hnsw_retrieval_ms) == len(tie_aware_recalls):
        raise ValueError("paired measurements must have equal counts")
    if any(not isfinite(value) or value < 0 for value in (*flat_retrieval_ms, *hnsw_retrieval_ms)):
        raise ValueError("timings must be finite and nonnegative")
    if any(
        value is not None and (not isfinite(value) or not 0 <= value <= 1)
        for value in tie_aware_recalls
    ):
        raise ValueError("recall must be unavailable or a probability")
    count = len(flat_retrieval_ms)
    flat_p95 = sorted(flat_retrieval_ms)[ceil(count * 0.95) - 1] if count else None
    hnsw_p95 = sorted(hnsw_retrieval_ms)[ceil(count * 0.95) - 1] if count else None
    minimum = min((value for value in tie_aware_recalls if value is not None), default=None)
    eligible = (
        repetitions >= 3
        and count > 0
        and fallback_count == 0
        and minimum is not None
        and minimum >= 0.95
        and all(value is not None for value in tie_aware_recalls)
        and flat_p95 is not None
        and hnsw_p95 is not None
        and hnsw_p95 < flat_p95
    )
    return {
        "eligible": eligible,
        "applied": False,
        "serving_default": "flat",
        "flat_retrieval_p95_ms": flat_p95,
        "hnsw_retrieval_p95_ms": hnsw_p95,
        "minimum_tie_aware_recall": minimum,
        "reason": "gate passed; explicit configuration decision required"
        if eligible
        else "gate not met; retain Flat",
        "requirements": "3 repetitions; lower full-retrieval P95; min recall >= 0.95; no fallback",
    }
