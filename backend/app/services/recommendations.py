"""Durable ad opportunities and immutable baseline selections."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import WorkflowError
from app.core.observability import stage, stages
from app.models.records import Ad, Advertiser, Recommendation, RequestOutcome, User
from app.ranking import BaselineCandidate, select_baseline
from app.retrieval.contracts import RetrievalResult, RetrievalUser
from app.retrieval.current import CurrentCandidateRetriever
from app.retrieval.limits import DEFAULT_CANDIDATE_LIMIT, CandidateLimit
from app.retrieval.snapshots import ActiveSnapshot


class RetrievalContext(BaseModel):
    """Compact immutable provenance; candidate payloads are not persisted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["exact", "hnsw", "exact_fallback", "nonpersonalized"]
    index_version: str | None
    hnsw_ef_search: int | None
    vocabulary_version: str
    vector_version: str
    requested_count: CandidateLimit
    returned_count: int = Field(ge=0, le=500)
    fallback_reason: str | None
    elapsed_ms: float = Field(ge=0)
    vector_elapsed_ms: float = Field(ge=0)
    metadata_elapsed_ms: float = Field(ge=0)
    fallback_elapsed_ms: float = Field(ge=0)
    searched_count: int = Field(ge=0)
    expansion_count: int = Field(ge=0)
    fallback_scanned_count: int = Field(ge=0)

    @classmethod
    def from_result(cls, result: RetrievalResult) -> "RetrievalContext":
        return cls.model_validate(result.model_dump(exclude={"candidates"}))


class AdSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    advertiser_id: int
    title: str
    description: str
    target_url: str
    category: str
    interests: tuple[str, ...]
    bid: Decimal
    score: int
    strategy: Literal["interest-overlap"] = "interest-overlap"
    strategy_version: Literal["baseline-v1"] = "baseline-v1"
    score_meaning: Literal["distinct_shared_interest_count"] = "distinct_shared_interest_count"
    predicted_ctr: None = None
    retrieval: RetrievalContext | None = None


@dataclass(frozen=True)
class RecommendationResult:
    user_id: int
    created_at: datetime
    recommendation_id: UUID | None
    selection: AdSelection | None


class _InventoryChanged(Exception):
    pass


@contextmanager
def _transaction(session: Session) -> Iterator[None]:
    with session.begin() as transaction:
        yield
        with stage("database_ms"):
            transaction.commit()


def _create_or_replay(
    session: Session,
    user_id: int,
    request_key: str,
    *,
    received_at: datetime,
    clock: Callable[[], datetime],
    snapshots: ActiveSnapshot,
    candidate_limit: int,
    search_limit: int,
) -> RecommendationResult:
    """Own the transaction; return only after both records have committed."""
    with _transaction(session):
        with stage("database_ms"):
            outcome = session.get(RequestOutcome, request_key)
        if outcome is not None:
            if outcome.user_id != user_id:
                raise WorkflowError(
                    409, "request_key_user_conflict", "Request key belongs to another user"
                )
            if received_at >= outcome.created_at + timedelta(hours=24):
                raise WorkflowError(
                    410, "request_key_expired", "Request key has expired; use a new key"
                )
            if outcome.recommendation_id is None:
                return RecommendationResult(outcome.user_id, outcome.created_at, None, None)
            with stage("database_ms"):
                saved = session.get(Recommendation, outcome.recommendation_id)
            assert saved is not None
            return RecommendationResult(
                outcome.user_id,
                outcome.created_at,
                saved.id,
                AdSelection.model_validate(saved.selected_ad),
            )
        with stage("database_ms"):
            user = session.scalar(select(User).where(User.id == user_id).with_for_update(read=True))
        if user is None:
            raise WorkflowError(404, "unknown_user", "Synthetic user was not found")
        with stage("selection_ms"):
            retrieved = CurrentCandidateRetriever(
                session, snapshots, search_limit=search_limit
            ).retrieve(
                RetrievalUser(
                    id=user.id, dataset_id=user.dataset_id, interests=tuple(user.interests)
                ),
                limit=candidate_limit,
            )
            timings = stages.get()
            if timings is not None:
                for name, value in (
                    ("retrieval_ms", retrieved.elapsed_ms),
                    ("vector_ms", retrieved.vector_elapsed_ms),
                    ("metadata_ms", retrieved.metadata_elapsed_ms),
                    ("fallback_ms", retrieved.fallback_elapsed_ms),
                ):
                    timings[name] = timings.get(name, 0.0) + value
            with stage("ranking_ms"):
                candidate = select_baseline(
                    user.interests,
                    (BaselineCandidate(ad.id, ad.interests, ad.bid) for ad in retrieved.candidates),
                )
        if candidate is None:
            created_at = clock()
            session.add(
                RequestOutcome(request_key=request_key, user_id=user_id, created_at=created_at)
            )
            return RecommendationResult(user_id, created_at, None, None)
        with stage("database_ms"):
            ad = session.scalar(
                select(Ad)
                .join(Advertiser, Ad.advertiser_id == Advertiser.id)
                .where(
                    Ad.id == candidate.id,
                    Ad.dataset_id == user.dataset_id,
                    Ad.active.is_(True),
                    Advertiser.active.is_(True),
                )
                .with_for_update(read=True, of=[Ad, Advertiser])
                .execution_options(populate_existing=True)
            )
        retrieved_ad = next(item for item in retrieved.candidates if item.id == candidate.id)
        if (
            ad is None
            or ad.bid != candidate.bid
            or tuple(ad.interests) != candidate.interests
            or ad.category != retrieved_ad.category
            or ad.advertiser_id != retrieved_ad.advertiser_id
        ):
            raise _InventoryChanged
        selection = AdSelection(
            id=ad.id,
            advertiser_id=ad.advertiser_id,
            title=ad.title,
            description=ad.description,
            target_url=ad.target_url,
            category=ad.category,
            interests=tuple(ad.interests),
            bid=ad.bid,
            score=len(set(user.interests).intersection(ad.interests)),
            retrieval=RetrievalContext.from_result(retrieved),
        )
        created_at = clock()
        recommendation = Recommendation(
            dataset_id=user.dataset_id,
            user_id=user_id,
            ad_id=ad.id,
            bid=selection.bid,
            selected_ad=selection.model_dump(mode="json"),
            created_at=created_at,
        )
        session.add(recommendation)
        with stage("database_ms"):
            session.flush()
        session.add(
            RequestOutcome(
                request_key=request_key,
                user_id=user_id,
                recommendation_id=recommendation.id,
                created_at=created_at,
            )
        )
        result = RecommendationResult(user_id, created_at, recommendation.id, selection)
    return result


def recommend(
    session: Session,
    user_id: int,
    request_key: str,
    *,
    clock: Callable[[], datetime] = utc_now,
    snapshots: ActiveSnapshot | None = None,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    search_limit: int = 4000,
) -> RecommendationResult:
    """Commit a new opportunity or replay its saved outcome after a racing writer."""
    if not request_key.strip() or len(request_key) > 255:
        raise WorkflowError(
            422, "invalid_request_key", "Request key must contain 1 to 255 characters"
        )
    received_at = clock()
    TypeAdapter(CandidateLimit).validate_python(candidate_limit)
    active = snapshots if snapshots is not None else ActiveSnapshot()
    try:
        for _ in range(3):
            try:
                return _create_or_replay(
                    session,
                    user_id,
                    request_key,
                    received_at=received_at,
                    clock=clock,
                    snapshots=active,
                    candidate_limit=candidate_limit,
                    search_limit=search_limit,
                )
            except _InventoryChanged:
                continue
            except IntegrityError as error:
                if (
                    isinstance(error.orig, UniqueViolation)
                    and error.orig.diag.constraint_name == "request_outcomes_pkey"
                ):
                    # The context manager has rolled back the entire losing transaction.
                    return _create_or_replay(
                        session,
                        user_id,
                        request_key,
                        received_at=received_at,
                        clock=clock,
                        snapshots=active,
                        candidate_limit=candidate_limit,
                        search_limit=search_limit,
                    )
                raise
        raise WorkflowError(
            503, "inventory_changing", "Inventory changed repeatedly; retry the request"
        )
    except (SQLAlchemyError, ValueError):
        raise WorkflowError(
            503, "recommendation_unavailable", "Recommendation storage is unavailable"
        ) from None
