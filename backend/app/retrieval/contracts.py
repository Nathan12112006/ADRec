"""Immutable inputs/results for replaceable candidate retrieval implementations."""

from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.retrieval.limits import DEFAULT_CANDIDATE_LIMIT, CandidateLimit
from app.retrieval.vectors import ad_vector, user_vector


class RetrievalCandidate(BaseModel):
    """Current detached ad metadata; eligibility still needs selection-time rechecking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = Field(strict=True, gt=0, le=2**63 - 1)
    dataset_id: UUID
    advertiser_id: int = Field(strict=True, gt=0, le=2**63 - 1)
    title: str
    description: str
    target_url: str
    category: str
    interests: tuple[str, ...]
    bid: Decimal = Field(ge=0, allow_inf_nan=False)
    similarity: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    active: Literal[True] = True
    advertiser_active: Literal[True] = True

    @model_validator(mode="after")
    def validate_topics(self) -> "RetrievalCandidate":
        ad_vector(self.interests, category=self.category)
        return self


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[RetrievalCandidate, ...]
    mode: Literal["exact", "hnsw", "exact_fallback", "nonpersonalized"]
    index_version: str | None = Field(default=None, min_length=1)
    vocabulary_version: Literal["topics-v1"] = "topics-v1"
    vector_version: Literal["binary-cosine-v1"] = "binary-cosine-v1"
    requested_count: CandidateLimit
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)
    vector_elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    metadata_elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    fallback_elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    searched_count: int = Field(default=0, strict=True, ge=0)
    expansion_count: int = Field(default=0, strict=True, ge=0)
    fallback_scanned_count: int = Field(default=0, strict=True, ge=0)
    fallback_reason: (
        Literal[
            "empty_interests",
            "missing_index",
            "corrupt_index",
            "incompatible_index",
            "stale_index",
            "insufficient_candidates",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_candidates(self) -> "RetrievalResult":
        if self.mode in ("exact", "hnsw"):
            if self.index_version is None or self.fallback_reason is not None:
                raise ValueError("indexed retrieval needs an index version and no fallback reason")
        else:
            if self.index_version is not None or self.fallback_reason is None:
                raise ValueError("fallback needs a reason and cannot claim an active index")
            if (self.mode == "nonpersonalized") != (self.fallback_reason == "empty_interests"):
                raise ValueError("empty interests require nonpersonalized fallback")
        ids = [candidate.id for candidate in self.candidates]
        if len(ids) > self.requested_count or len(set(ids)) != len(ids):
            raise ValueError("candidates must be distinct and within the requested limit")
        if self.mode == "nonpersonalized":
            if any(candidate.similarity is not None for candidate in self.candidates):
                raise ValueError("nonpersonalized retrieval has no cosine score")
            bid_keys = [(-candidate.bid, candidate.id) for candidate in self.candidates]
            if bid_keys != sorted(bid_keys):
                raise ValueError("nonpersonalized candidates must be ordered by bid then ad ID")
        else:
            keys: list[tuple[float, int]] = []
            for candidate in self.candidates:
                if candidate.similarity is None:
                    raise ValueError("cosine retrieval requires similarity")
                keys.append((-candidate.similarity, candidate.id))
            if keys != sorted(keys):
                raise ValueError("candidates must be ordered by descending similarity then ad ID")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def returned_count(self) -> int:
        return len(self.candidates)


class RetrievalUser(BaseModel):
    """The synthetic user identity and interests needed by candidate retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = Field(strict=True, gt=0, le=2**63 - 1)
    dataset_id: UUID
    interests: tuple[str, ...]

    @model_validator(mode="after")
    def validate_interests(self) -> "RetrievalUser":
        user_vector(self.interests)
        return self


class CandidateRetriever(Protocol):
    """Retrieve distinct current eligible candidates; ranking chooses the winner.

    Implementations validate limit, use nonpersonalized fallback for empty interests,
    time the full retrieval including metadata/filtering/fallback, and propagate database
    failures (never convert them to an empty result). Selection rechecks eligibility.
    """

    def retrieve(
        self,
        user: RetrievalUser,
        limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> RetrievalResult: ...
