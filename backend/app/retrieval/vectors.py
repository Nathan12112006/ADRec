"""Binary topic membership normalized for cosine inner-product search."""

from collections.abc import Iterable
from math import fsum, isclose, isfinite, sqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.topics import TOPICS


class TopicVector(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    values: tuple[float, ...]
    topics: tuple[str, ...] = TOPICS
    vocabulary_version: Literal["topics-v1"] = "topics-v1"
    vector_version: Literal["binary-cosine-v1"] = "binary-cosine-v1"

    @model_validator(mode="after")
    def validate_membership(self) -> "TopicVector":
        if self.topics != TOPICS:
            raise ValueError("vocabulary order must match topics-v1")
        if len(self.values) != len(TOPICS):
            raise ValueError("vector dimension must match the topic vocabulary")
        if any(not isfinite(value) or value < 0 or value > 1 for value in self.values):
            raise ValueError("vector values must be finite and between zero and one")
        members = [value for value in self.values if value > 0]
        if not members:
            raise ValueError("zero vectors cannot represent catalog ads or cosine queries")
        expected = 1 / sqrt(len(members))
        # Accept float32 round trips while rejecting non-unit or weighted membership.
        if any(not isclose(value, expected, rel_tol=0, abs_tol=1e-6) for value in members):
            raise ValueError("vector must contain normalized binary membership")
        return self

    def similarity(self, other: "TopicVector") -> float:
        """Inner product of normalized membership vectors is cosine similarity."""
        score = fsum(left * right for left, right in zip(self.values, other.values, strict=True))
        return min(1.0, score)  # Normalization/float32 rounding can overshoot one slightly.


def user_vector(interests: Iterable[str]) -> TopicVector | None:
    """Empty interests explicitly bypass vector search."""
    membership = set(interests)
    if not membership.issubset(TOPICS):
        raise ValueError("unknown topic in membership")
    if not membership:
        return None
    scale = 1 / sqrt(len(membership))
    return TopicVector(values=tuple(scale if topic in membership else 0.0 for topic in TOPICS))


def ad_vector(interests: Iterable[str], *, category: str) -> TopicVector:
    """Category contributes one membership dimension, even when already an interest."""
    vector = user_vector((*interests, category))
    assert vector is not None
    return vector
