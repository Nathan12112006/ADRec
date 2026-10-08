"""Durable ad opportunities and immutable baseline selections."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import WorkflowError
from app.db.selection import select_baseline_ad
from app.models.records import Ad, Advertiser, Recommendation, RequestOutcome, User


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


@dataclass(frozen=True)
class RecommendationResult:
    user_id: int
    created_at: datetime
    recommendation_id: UUID | None
    selection: AdSelection | None


class _InventoryChanged(Exception):
    pass


def _create_or_replay(
    session: Session,
    user_id: int,
    request_key: str,
    *,
    received_at: datetime,
    clock: Callable[[], datetime],
) -> RecommendationResult:
    """Own the transaction; return only after both records have committed."""
    with session.begin():
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
            saved = session.get(Recommendation, outcome.recommendation_id)
            assert saved is not None
            return RecommendationResult(
                outcome.user_id,
                outcome.created_at,
                saved.id,
                AdSelection.model_validate(saved.selected_ad),
            )
        user = session.scalar(select(User).where(User.id == user_id).with_for_update(read=True))
        if user is None:
            raise WorkflowError(404, "unknown_user", "Synthetic user was not found")
        candidate = select_baseline_ad(session, user.interests, dataset_id=user.dataset_id)
        if candidate is None:
            created_at = clock()
            session.add(
                RequestOutcome(request_key=request_key, user_id=user_id, created_at=created_at)
            )
            return RecommendationResult(user_id, created_at, None, None)
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
        if ad is None or ad.bid != candidate.bid or tuple(ad.interests) != candidate.interests:
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
) -> RecommendationResult:
    """Commit a new opportunity or replay its saved outcome after a racing writer."""
    if not request_key.strip() or len(request_key) > 255:
        raise WorkflowError(
            422, "invalid_request_key", "Request key must contain 1 to 255 characters"
        )
    received_at = clock()
    try:
        for _ in range(3):
            try:
                return _create_or_replay(
                    session, user_id, request_key, received_at=received_at, clock=clock
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
                        session, user_id, request_key, received_at=received_at, clock=clock
                    )
                raise
        raise WorkflowError(
            503, "inventory_changing", "Inventory changed repeatedly; retry the request"
        )
    except (SQLAlchemyError, ValueError):
        raise WorkflowError(
            503, "recommendation_unavailable", "Recommendation storage is unavailable"
        ) from None
