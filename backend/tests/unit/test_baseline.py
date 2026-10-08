from decimal import Decimal

import pytest

from app.ranking import BaselineCandidate, select_baseline


def test_distinct_shared_interests_outrank_bid() -> None:
    repeated = BaselineCandidate(1, ("gaming", "gaming", "gaming"), Decimal("5"))
    relevant = BaselineCandidate(2, ("gaming", "music"), Decimal("1"))
    assert select_baseline(["gaming", "gaming", "music"], [repeated, relevant]) == relevant


@pytest.mark.parametrize("user_interests", [[], ["travel"]])
@pytest.mark.parametrize("reverse", [False, True])
def test_no_overlap_uses_exact_bid_then_ascending_id(
    user_interests: list[str], reverse: bool
) -> None:
    winner = BaselineCandidate(2, ("music",), Decimal("1.0002"))
    candidates = [
        BaselineCandidate(1, ("music",), Decimal("1.0001")),
        BaselineCandidate(3, ("music",), Decimal("1.0002")),
        winner,
    ]
    if reverse:
        candidates.reverse()
    assert select_baseline(iter(user_interests), iter(candidates)) == winner


def test_inactive_ads_and_advertisers_cannot_win() -> None:
    winner = BaselineCandidate(3, (), Decimal("0"))
    candidates = [
        BaselineCandidate(1, ("music",), Decimal("5"), active=False),
        BaselineCandidate(2, ("music",), Decimal("5"), advertiser_active=False),
        winner,
    ]
    assert select_baseline(["music"], candidates) == winner


@pytest.mark.parametrize(
    "candidates",
    [[], [BaselineCandidate(1, (), Decimal("0"), active=False)]],
)
def test_empty_eligible_inventory_returns_no_ad(candidates: list[BaselineCandidate]) -> None:
    assert select_baseline(["music"], iter(candidates)) is None


def test_zero_bids_remain_eligible_and_overlap_still_wins() -> None:
    winner = BaselineCandidate(2, ("music",), Decimal("0"))
    assert select_baseline(["music"], [BaselineCandidate(1, (), Decimal("5")), winner]) == winner


@pytest.mark.parametrize("bid", ["-1", "NaN", "sNaN", "Infinity", "-Infinity"])
def test_invalid_eligible_bids_are_rejected(bid: str) -> None:
    with pytest.raises(ValueError, match="finite nonnegative"):
        select_baseline([], [BaselineCandidate(1, (), Decimal(bid))])
