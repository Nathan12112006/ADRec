"""Deterministic interest-overlap selection without model inference."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BaselineCandidate:
    id: int
    interests: tuple[str, ...]
    bid: Decimal
    active: bool = True
    advertiser_active: bool = True


def select_baseline(
    user_interests: Iterable[str], candidates: Iterable[BaselineCandidate]
) -> BaselineCandidate | None:
    """Choose maximum distinct overlap, then bid, then minimum ad ID."""
    interests = set(user_interests)
    winner = None
    best_key: tuple[int, Decimal, int] | None = None
    for candidate in candidates:
        if not candidate.active or not candidate.advertiser_active:
            continue
        if not candidate.bid.is_finite() or candidate.bid < 0:
            raise ValueError("eligible ad bid must be finite nonnegative decimal money")
        overlap = len(interests.intersection(candidate.interests))
        key = (overlap, candidate.bid, -candidate.id)
        if best_key is None or key > best_key:
            winner, best_key = candidate, key
    return winner
