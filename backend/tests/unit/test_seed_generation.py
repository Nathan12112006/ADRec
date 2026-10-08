from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.seeding import SeedConfig, generate_entities


def test_seed_reproduces_entities_references_and_topic_relationships() -> None:
    config = SeedConfig(seed=42, users=7, advertisers=3, ads=15)
    first = list(generate_entities(config))
    assert first == list(generate_entities(config))
    assert [kind for kind, _ in first].count("users") == 7
    assert [kind for kind, _ in first].count("advertisers") == 3
    assert [kind for kind, _ in first].count("ads") == 15
    advertisers = {row["id"] for kind, row in first if kind == "advertisers"}
    for kind, row in first:
        if kind == "ads":
            assert row["advertiser_id"] in advertisers
            assert isinstance(row["bid"], Decimal) and row["bid"] >= 0
            assert row["category"] in row["interests"]
            assert row["active"] is True


def test_profile_count_does_not_change_ad_random_stream() -> None:
    short = SeedConfig(users=2, advertisers=3, ads=10)
    longer = SeedConfig(users=20, advertisers=3, ads=10)

    def payloads(config: SeedConfig) -> list[dict[str, object]]:
        return [
            {
                key: value
                for key, value in row.items()
                if key not in {"id", "dataset_id", "advertiser_id"}
            }
            for kind, row in generate_entities(config)
            if kind == "ads"
        ]

    assert payloads(short) == payloads(longer)
    assert short.dataset_id != longer.dataset_id


@pytest.mark.parametrize("counts", [{"users": -1}, {"advertisers": 0}, {"ads": -1}])
def test_invalid_counts_are_rejected(counts: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        SeedConfig(**counts)


def test_defaults_and_zero_count_dataset_are_explicit() -> None:
    defaults = SeedConfig()
    assert (defaults.users, defaults.advertisers, defaults.ads) == (100, 20, 1000)
    assert defaults.manifest()["historical_impressions"] == 0
    assert list(generate_entities(SeedConfig(users=0, advertisers=0, ads=0))) == []
