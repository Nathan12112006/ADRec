"""Durable ad opportunities and coherent immutable ranked selections."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.cache.profiles import CachedUserProfile, RedisProfileCache
from app.core.clock import utc_now
from app.core.errors import WorkflowError
from app.core.observability import stage, stages
from app.ctr.features import FEATURE_VERSION
from app.ctr.serving import CTRModel, CTRUnavailable
from app.ctr.training import MODEL_VERSION
from app.experiments.assignment import AssignmentConfig, assign_variant
from app.experiments.management import lock_experiment_routing
from app.models.records import Ad, Advertiser, Experiment, Recommendation, RequestOutcome, User
from app.ranking.strategies import ExpectedValue, InterestOverlap, RankingStrategy
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
    fallback_reason: (
        Literal[
            "empty_interests",
            "missing_index",
            "corrupt_index",
            "incompatible_index",
            "stale_index",
            "insufficient_candidates",
            "experiment_exact",
        ]
        | None
    )
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
    score: Decimal | int
    strategy: Literal["interest-overlap", "expected-value"] = "interest-overlap"
    strategy_version: str = "baseline-v1"
    score_meaning: Literal[
        "distinct_shared_interest_count", "expected_simulated_dollars_per_impression"
    ] = "distinct_shared_interest_count"
    predicted_ctr: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    shared_interest_count: int | None = Field(default=None, ge=0)
    model_id: str | None = None
    model_version: str | None = None
    feature_version: str | None = None
    retrieval: RetrievalContext | None = None


@dataclass(frozen=True)
class RecommendationResult:
    user_id: int
    created_at: datetime
    recommendation_id: UUID | None
    selection: AdSelection | None
    experiment_id: UUID | None = None
    experiment_variant: Literal["control", "treatment"] | None = None
    replayed: bool = field(default=False, compare=False)
    retrieval: RetrievalContext | None = field(default=None, compare=False)


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
    strategy: RankingStrategy,
    ctr_model: CTRModel | None,
    profile_cache: RedisProfileCache | None,
    request_context: dict[str, Any] | None,
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
                if request_context is not None:
                    request_context.update(
                        experiment_id=(
                            str(outcome.experiment_id) if outcome.experiment_id else None
                        ),
                        experiment_variant=outcome.experiment_variant,
                    )
                return RecommendationResult(
                    outcome.user_id,
                    outcome.created_at,
                    None,
                    None,
                    outcome.experiment_id,
                    outcome.experiment_variant,
                    True,
                )
            with stage("database_ms"):
                saved = session.get(Recommendation, outcome.recommendation_id)
            assert saved is not None
            if request_context is not None:
                request_context.update(
                    experiment_id=(str(saved.experiment_id) if saved.experiment_id else None),
                    experiment_variant=saved.experiment_variant,
                )
            return RecommendationResult(
                outcome.user_id,
                outcome.created_at,
                saved.id,
                AdSelection.model_validate(saved.selected_ad),
                saved.experiment_id,
                saved.experiment_variant,
                True,
            )
        lock_experiment_routing(session, exclusive=False)
        experiment = session.scalar(
            select(Experiment).where(Experiment.status == "running").with_for_update(read=True)
        )
        if profile_cache is None or not profile_cache.enabled:
            with stage("database_ms"):
                user = session.scalar(
                    select(User).where(User.id == user_id).with_for_update(read=True)
                )
            if user is None:
                raise WorkflowError(404, "unknown_user", "Synthetic user was not found")
            profile = CachedUserProfile(
                dataset_id=user.dataset_id,
                user_id=user.id,
                interests=tuple(user.interests),
                category_preferences=tuple(user.category_preferences),
                age_group=user.age_group,
                country=user.country,
                device=user.device,
            )
        else:
            with stage("database_ms"):
                dataset_id = session.scalar(
                    select(User.dataset_id).where(User.id == user_id).with_for_update(read=True)
                )
            if dataset_id is None:
                raise WorkflowError(404, "unknown_user", "Synthetic user was not found")

            def load_profile() -> CachedUserProfile | None:
                with stage("database_ms"):
                    user = session.scalar(
                        select(User)
                        .where(User.id == user_id, User.dataset_id == dataset_id)
                        .with_for_update(read=True)
                    )
                if user is None:
                    return None
                return CachedUserProfile(
                    dataset_id=user.dataset_id,
                    user_id=user.id,
                    interests=tuple(user.interests),
                    category_preferences=tuple(user.category_preferences),
                    age_group=user.age_group,
                    country=user.country,
                    device=user.device,
                )

            lookup = profile_cache.get_or_load(dataset_id, user_id, load_profile)
            cached_profile = lookup.profile
            if cached_profile is None:
                raise WorkflowError(404, "unknown_user", "Synthetic user was not found")
            profile = cached_profile
        experiment_id: UUID | None = None
        experiment_variant: Literal["control", "treatment"] | None = None
        active_strategy = strategy
        active_candidate_limit = candidate_limit
        active_search_limit = search_limit
        active_ef_search: int | None = None
        force_exact = False
        if experiment is not None:
            experiment_id = experiment.id
            experiment_variant = assign_variant(
                user_id, AssignmentConfig.model_validate(experiment)
            )
        if request_context is not None:
            request_context.update(
                experiment_id=(str(experiment_id) if experiment_id else None),
                experiment_variant=experiment_variant,
            )
        if experiment is not None:
            selected_strategy = (
                experiment.control_strategy
                if experiment_variant == "control"
                else experiment.treatment_strategy
            )
            if (
                ctr_model is None
                or ctr_model.model_id != experiment.model_id
                or MODEL_VERSION != experiment.model_version
                or FEATURE_VERSION != experiment.feature_version
            ):
                raise CTRUnavailable()
            active_strategy = (
                ExpectedValue(ctr_model)
                if selected_strategy == "expected-value"
                else InterestOverlap()
            )
            active_candidate_limit = experiment.candidate_limit
            active_search_limit = experiment.search_limit
            if experiment.retrieval_mode == "exact":
                force_exact = True
            else:
                snapshot = snapshots.status().snapshot
                if snapshot is None or snapshot.manifest.hnsw is None:
                    force_exact = True
                else:
                    active_ef_search = experiment.hnsw_ef_search
        with stage("selection_ms"):
            retrieved = CurrentCandidateRetriever(
                session,
                snapshots,
                search_limit=active_search_limit,
                ef_search=active_ef_search,
                force_exact=force_exact,
            ).retrieve(
                RetrievalUser(
                    id=profile.user_id,
                    dataset_id=profile.dataset_id,
                    interests=profile.interests,
                ),
                limit=active_candidate_limit,
            )
            if request_context is not None:
                request_context.update(
                    retrieval_mode=retrieved.mode,
                    fallback_reason=retrieved.fallback_reason,
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
                ranking = active_strategy.rank(
                    {
                        "interests": profile.interests,
                        "device": profile.device,
                        "age_group": profile.age_group,
                    },
                    [ad.model_dump() for ad in retrieved.candidates],
                )
                candidate = ranking.candidates[0] if ranking.candidates else None
        if candidate is None:
            created_at = clock()
            session.add(
                RequestOutcome(
                    request_key=request_key,
                    user_id=user_id,
                    experiment_id=experiment_id,
                    experiment_variant=experiment_variant,
                    created_at=created_at,
                )
            )
            return RecommendationResult(
                user_id,
                created_at,
                None,
                None,
                experiment_id,
                experiment_variant,
                retrieval=RetrievalContext.from_result(retrieved),
            )
        with stage("database_ms"):
            ad = session.scalar(
                select(Ad)
                .join(Advertiser, Ad.advertiser_id == Advertiser.id)
                .where(
                    Ad.id == candidate.ad_id,
                    Ad.dataset_id == profile.dataset_id,
                    Ad.active.is_(True),
                    Advertiser.active.is_(True),
                )
                .with_for_update(read=True, of=[Ad, Advertiser])
                .execution_options(populate_existing=True)
            )
        retrieved_ad = next(item for item in retrieved.candidates if item.id == candidate.ad_id)
        if (
            ad is None
            or ad.bid != candidate.bid
            or tuple(ad.interests) != retrieved_ad.interests
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
            score=candidate.score,
            strategy=ranking.strategy,
            strategy_version=ranking.strategy_version,
            score_meaning=ranking.score_meaning,
            predicted_ctr=candidate.predicted_ctr,
            shared_interest_count=candidate.shared_interest_count,
            model_id=ranking.model_id,
            model_version=ranking.model_version,
            feature_version=ranking.feature_version,
            retrieval=RetrievalContext.from_result(retrieved),
        )
        created_at = clock()
        recommendation = Recommendation(
            dataset_id=profile.dataset_id,
            user_id=user_id,
            ad_id=ad.id,
            bid=selection.bid,
            selected_ad=selection.model_dump(mode="json"),
            experiment_id=experiment_id,
            experiment_variant=experiment_variant,
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
                experiment_id=experiment_id,
                experiment_variant=experiment_variant,
                created_at=created_at,
            )
        )
        result = RecommendationResult(
            user_id,
            created_at,
            recommendation.id,
            selection,
            experiment_id,
            experiment_variant,
        )
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
    strategy: RankingStrategy | None = None,
    ctr_model: CTRModel | None = None,
    profile_cache: RedisProfileCache | None = None,
    request_context: dict[str, Any] | None = None,
) -> RecommendationResult:
    """Commit a new opportunity or replay its saved outcome after a racing writer."""
    if not request_key.strip() or len(request_key) > 255:
        raise WorkflowError(
            422, "invalid_request_key", "Request key must contain 1 to 255 characters"
        )
    received_at = clock()
    TypeAdapter(CandidateLimit).validate_python(candidate_limit)
    active = snapshots if snapshots is not None else ActiveSnapshot()
    ranking_strategy = strategy if strategy is not None else InterestOverlap()
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
                    strategy=ranking_strategy,
                    ctr_model=ctr_model,
                    profile_cache=profile_cache,
                    request_context=request_context,
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
                        strategy=ranking_strategy,
                        ctr_model=ctr_model,
                        profile_cache=profile_cache,
                        request_context=request_context,
                    )
                raise
        raise WorkflowError(
            503, "inventory_changing", "Inventory changed repeatedly; retry the request"
        )
    except (SQLAlchemyError, ValueError):
        raise WorkflowError(
            503, "recommendation_unavailable", "Recommendation storage is unavailable"
        ) from None
