"""Independent synthetic behavior assumptions, shared by offline and future live sampling."""

import hashlib
import math
from random import Random

from pydantic import BaseModel, ConfigDict, Field

OUTCOME_VERSION = "click-world-v1"


class OutcomeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    intercept: float = Field(default=-4.2, ge=-20, le=20)
    shared_interest_weight: float = Field(default=0.45, ge=0, le=5)
    category_preference_weight: float = Field(default=0.8, ge=0, le=5)
    mobile_offset: float = Field(default=0.15, ge=-5, le=5)
    tablet_offset: float = Field(default=-0.1, ge=-5, le=5)
    hidden_scale: float = Field(default=0.15, ge=0, le=0.5)


class OutcomeUser(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int = Field(gt=0)
    interests: tuple[str, ...]
    category_preferences: tuple[str, ...]
    device: str


class OutcomeAd(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int = Field(gt=0)
    category: str
    interests: tuple[str, ...]


def stream_seed(seed: int, stream: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{OUTCOME_VERSION}/{seed}/{stream}".encode()).digest(), "big"
    )


class OutcomeGenerator:
    def __init__(self, config: OutcomeConfig, *, seed: int) -> None:
        self.config = config
        self.seed = seed

    def _preference(self, kind: str, identity: int) -> float:
        draw = Random(stream_seed(self.seed, f"hidden/{kind}/{identity}")).random()
        return (2 * draw - 1) * self.config.hidden_scale

    def probability(self, user: OutcomeUser, ad: OutcomeAd) -> float:
        overlap = len(set(user.interests) & set(ad.interests))
        config = self.config
        device = {"mobile": config.mobile_offset, "tablet": config.tablet_offset}.get(
            user.device, 0
        )
        logit = (
            config.intercept
            + config.shared_interest_weight * overlap
            + config.category_preference_weight * (ad.category in user.category_preferences)
            + device
            + self._preference("user", user.id)
            + self._preference("ad", ad.id)
        )
        return 1 / (1 + math.exp(-logit))

    def sample(self, user: OutcomeUser, ad: OutcomeAd, *, opportunity: str) -> int:
        """Stable per-opportunity draws are independent of request completion order."""
        draw = Random(stream_seed(self.seed, f"outcomes/{opportunity}")).random()
        return int(draw < self.probability(user, ad))
