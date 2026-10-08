from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.selection import select_baseline_ad
from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset


@pytest.fixture
def inventory(database: Database) -> Iterator[Session]:
    # Isolate visibility without deleting durable history or committing inventory edits.
    with database.session() as session:
        session.execute(update(Ad).values(active=False))
        dataset = Dataset(seed=4, generator_version="selector-test", configuration={})
        session.add(dataset)
        session.flush()
        advertisers = [
            Advertiser(dataset_id=dataset.id, name="active", active=True),
            Advertiser(dataset_id=dataset.id, name="inactive", active=False),
        ]
        session.add_all(advertisers)
        session.flush()
        for index, (interests, bid, active, advertiser) in enumerate(
            [
                (["music", "music"], "5", True, advertisers[0]),
                (["music", "gaming"], "0", True, advertisers[0]),
                (["music", "gaming"], "9", False, advertisers[0]),
                (["music", "gaming"], "9", True, advertisers[1]),
            ]
        ):
            session.add(
                Ad(
                    dataset_id=dataset.id,
                    advertiser_id=advertiser.id,
                    title=str(index),
                    description="fixture",
                    target_url="https://example.invalid",
                    category="music",
                    interests=interests,
                    bid=Decimal(bid),
                    active=active,
                )
            )
        session.flush()
        yield session


def test_database_selects_distinct_overlap_and_excludes_inactive_inventory(
    inventory: Session,
) -> None:
    selected = select_baseline_ad(inventory, ["music", "gaming"])
    assert selected is not None
    assert selected.interests == ("music", "gaming")
    assert selected.bid == Decimal("0")


def test_database_empty_interests_choose_highest_bid(inventory: Session) -> None:
    selected = select_baseline_ad(inventory, [])
    assert selected is not None
    assert selected.interests == ("music", "music")
    assert selected.bid == Decimal("5")


def test_database_returns_no_ad_for_empty_eligible_inventory(inventory: Session) -> None:
    inventory.execute(update(Ad).values(active=False))
    assert select_baseline_ad(inventory, ["music"]) is None


def test_database_equal_overlap_and_bid_choose_smallest_id(inventory: Session) -> None:
    inventory.execute(update(Ad).where(Ad.active.is_(True)).values(bid=Decimal("0")))
    selected = select_baseline_ad(inventory, [])
    assert selected is not None
    # First inserted active ad has the smaller identity; the other has more interests.
    assert selected.interests == ("music", "music")
    assert selected.bid == Decimal("0")
