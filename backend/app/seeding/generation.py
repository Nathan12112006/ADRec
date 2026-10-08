"""Versioned synthetic entity generation, independent of ranking and click outcomes."""

import hashlib
import json
import platform
import random
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

GENERATOR_VERSION = "entities-v1"
TOPICS = (
    "technology",
    "gaming",
    "fitness",
    "travel",
    "food",
    "fashion",
    "sports",
    "finance",
    "education",
    "music",
    "movies",
    "photography",
    "cars",
)
RELATED = {topic: [topic] for topic in TOPICS}
RELATED.update(
    {
        "technology": ["technology", "gaming", "photography"],
        "gaming": ["gaming", "technology"],
        "fitness": ["fitness", "sports"],
        "travel": ["travel", "photography", "food"],
        "sports": ["sports", "fitness"],
        "cars": ["cars", "technology"],
    }
)
AGE_GROUPS = ("18-24", "25-34", "35-44", "45-54", "55+")
COUNTRIES = ("US", "CA", "GB", "DE", "AU")
DEVICES = ("mobile", "desktop", "tablet")


class SeedConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    seed: int = Field(default=42, ge=-(2**63), lt=2**63)
    users: int = Field(default=100, ge=0)
    advertisers: int = Field(default=20, ge=0)
    ads: int = Field(default=1000, ge=0)

    @model_validator(mode="after")
    def require_advertisers(self) -> "SeedConfig":
        if self.ads and not self.advertisers:
            raise ValueError("ads require at least one advertiser")
        return self

    def manifest(self) -> dict[str, Any]:
        return {
            **self.model_dump(),
            "generator_version": GENERATOR_VERSION,
            "python_version": platform.python_version(),
            "topics": list(TOPICS),
            "category_interests": {key: list(value) for key, value in RELATED.items()},
            "age_groups": list(AGE_GROUPS),
            "countries": list(COUNTRIES),
            "devices": list(DEVICES),
            "sampling": "uniform; independent users/advertisers/ads random streams",
            "user_interest_count": [1, 5],
            "category_preference_count": [1, 3],
            "bid_cents": [25, 500],
            "active_percent": 100,
            "historical_impressions": 0,
            "historical_clicks": 0,
            "simulated_time_range": None,
            "split_definitions": None,
        }

    @property
    def dataset_id(self) -> UUID:
        return uuid5(
            NAMESPACE_URL, "adflow/entities/" + json.dumps(self.manifest(), sort_keys=True)
        )


def _entity_id(dataset_id: UUID, kind: str, index: int) -> int:
    digest = hashlib.sha256(f"{dataset_id}/{kind}/{index}".encode()).digest()
    return (int.from_bytes(digest[:8], "big") % (2**63 - 1)) + 1


def _stream(seed: int, kind: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(f"{seed}/{kind}".encode()).digest(), "big"))


def generate_entities(config: SeedConfig) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield parents before children; memory stays independent of entity counts."""
    dataset_id = config.dataset_id
    users = _stream(config.seed, "users")
    for index in range(config.users):
        interests = users.sample(TOPICS, users.randint(1, 5))
        yield (
            "users",
            {
                "id": _entity_id(dataset_id, "users", index),
                "dataset_id": dataset_id,
                "interests": interests,
                "category_preferences": users.sample(
                    interests, users.randint(1, min(3, len(interests)))
                ),
                "age_group": users.choice(AGE_GROUPS),
                "country": users.choice(COUNTRIES),
                "device": users.choice(DEVICES),
            },
        )
    advertisers = _stream(config.seed, "advertisers")
    for index in range(config.advertisers):
        yield (
            "advertisers",
            {
                "id": _entity_id(dataset_id, "advertisers", index),
                "dataset_id": dataset_id,
                "name": f"Synthetic {advertisers.choice(TOPICS).title()} Advertiser {index + 1}",
                "active": True,
            },
        )
    ads = _stream(config.seed, "ads")
    for index in range(config.ads):
        category = ads.choice(TOPICS)
        yield (
            "ads",
            {
                "id": _entity_id(dataset_id, "ads", index),
                "dataset_id": dataset_id,
                "advertiser_id": _entity_id(
                    dataset_id, "advertisers", ads.randrange(config.advertisers)
                ),
                "title": f"Synthetic {category.title()} Offer {index + 1}",
                "description": f"Fictional {category} advertisement for the AdFlow demo.",
                "target_url": f"https://example.test/ads/{index + 1}",
                "category": category,
                "interests": list(RELATED[category]),
                "bid": Decimal(ads.randint(25, 500)) / 100,
                "active": True,
            },
        )
