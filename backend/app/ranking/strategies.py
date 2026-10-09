"""Ordered ranking over detached eligible candidates; callers own selection/persistence."""

from collections.abc import Mapping, Sequence
from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal, localcontext
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.ctr.serving import CTRModel


class _Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int = Field(strict=True, gt=0)
    interests: tuple[str, ...] = ()
    bid: Decimal = Field(ge=0, allow_inf_nan=False)


class ScoredCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    ad_id: int
    bid: Decimal
    shared_interest_count: int
    score: int | Decimal
    predicted_ctr: float | None = None


class RankingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[ScoredCandidate, ...]
    strategy: Literal["interest-overlap", "expected-value"]
    strategy_version: str
    score_meaning: Literal[
        "distinct_shared_interest_count", "expected_simulated_dollars_per_impression"
    ]
    model_id: str | None = None
    model_version: str | None = None
    feature_version: str | None = None


class RankingStrategy(Protocol):
    def rank(
        self, user: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
    ) -> RankingResult: ...


def _validate_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[_Candidate]:
    validated = [_Candidate.model_validate(row) for row in candidates]
    if len({ad.id for ad in validated}) != len(validated):
        raise ValueError("ranking candidates must have distinct ad IDs")
    return validated


def _order(scored: list[ScoredCandidate]) -> tuple[ScoredCandidate, ...]:
    return tuple(
        sorted(
            scored,
            key=lambda ad: (
                Decimal(ad.score).copy_negate(),
                -ad.shared_interest_count,
                ad.bid.copy_negate(),
                ad.ad_id,
            ),
        )
    )


def _expected_score(probability: float, bid: Decimal) -> Decimal:
    probability_decimal = Decimal(str(probability))
    precision = len(probability_decimal.as_tuple().digits) + len(bid.as_tuple().digits)
    with localcontext(Context(prec=precision, Emax=MAX_EMAX, Emin=MIN_EMIN)):
        return probability_decimal * bid


class InterestOverlap:
    def rank(
        self, user: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
    ) -> RankingResult:
        interests = set(user.get("interests") or ())
        scored = []
        for candidate in _validate_candidates(candidates):
            overlap = len(interests.intersection(candidate.interests))
            scored.append(
                ScoredCandidate(
                    ad_id=candidate.id,
                    bid=candidate.bid,
                    shared_interest_count=overlap,
                    score=overlap,
                )
            )
        return RankingResult(
            candidates=_order(scored),
            strategy="interest-overlap",
            strategy_version="baseline-v1",
            score_meaning="distinct_shared_interest_count",
        )


class ExpectedValue:
    def __init__(self, model: CTRModel) -> None:
        self._model = model

    def rank(
        self, user: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
    ) -> RankingResult:
        if not candidates:
            return RankingResult(
                candidates=(),
                strategy="expected-value",
                strategy_version="expected-value-v1",
                score_meaning="expected_simulated_dollars_per_impression",
            )
        validated = _validate_candidates(candidates)
        prediction = self._model.predict_batch(user, candidates)
        interests = set(user.get("interests") or ())
        scored = [
            ScoredCandidate(
                ad_id=candidate.id,
                bid=candidate.bid,
                shared_interest_count=len(interests.intersection(candidate.interests)),
                score=_expected_score(probability, candidate.bid),
                predicted_ctr=probability,
            )
            for candidate, probability in zip(validated, prediction.probabilities, strict=True)
        ]
        return RankingResult(
            candidates=_order(scored),
            strategy="expected-value",
            strategy_version="expected-value-v1",
            score_meaning="expected_simulated_dollars_per_impression",
            model_id=prediction.model_id,
            model_version=prediction.model_version,
            feature_version=prediction.feature_version,
        )
