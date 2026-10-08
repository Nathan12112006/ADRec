from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_clock, get_database, get_session, get_settings
from app.core.errors import WorkflowError
from app.core.observability import stage
from app.db.session import Database
from app.schemas.lifecycle import (
    ErrorResponse,
    EventRequest,
    EventResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.events import EventType, record_event
from app.services.recommendations import recommend

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_session)]
ClockDependency = Annotated[Callable[[], datetime], Depends(get_clock)]
ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (404, 409, 410, 422, 503)
}


@router.post(
    "/api/v1/recommendations",
    response_model=RecommendationResponse,
    responses={**ERRORS, 204: {"description": "No eligible ad"}},
)
def recommendations(
    body: RecommendationRequest,
    request: Request,
    session: SessionDependency,
    clock: ClockDependency,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=255)],
) -> RecommendationResponse | Response:
    request.state.context["user_id"] = body.user_id
    request.state.context["request_key_sha256"] = sha256(idempotency_key.encode()).hexdigest()
    if len(request.headers.getlist("idempotency-key")) != 1:
        raise WorkflowError(422, "invalid_request_key", "Provide exactly one Idempotency-Key")
    with stage("recommendation_ms"):
        settings = get_settings(request)
        result = recommend(
            session,
            body.user_id,
            idempotency_key,
            clock=clock,
            snapshots=request.app.state.snapshots,
            candidate_limit=settings.retrieval_candidate_limit,
            search_limit=settings.retrieval_search_limit,
        )
    if result.recommendation_id is None:
        request.state.context["outcome"] = "no_ad"
        return Response(status_code=204)
    assert result.selection is not None
    request.state.context.update(
        recommendation_id=str(result.recommendation_id),
        ad_id=result.selection.id,
        strategy=result.selection.strategy,
        score=result.selection.score,
        outcome="selected",
    )
    return RecommendationResponse(
        recommendation_id=result.recommendation_id,
        user_id=result.user_id,
        created_at=result.created_at,
        selection=result.selection,
    )


def accept_event(
    body: EventRequest,
    request: Request,
    session: Session,
    event_type: EventType,
    clock: Callable[[], datetime],
) -> EventResponse:
    request.state.context.update(
        recommendation_id=str(body.recommendation_id), event_type=event_type
    )
    with stage("event_ms"):
        result = record_event(session, body.recommendation_id, event_type, clock=clock)
    request.state.context.update(user_id=result.user_id, ad_id=result.ad_id, outcome="accepted")
    return EventResponse(**asdict(result))


@router.post("/api/v1/events/impression", response_model=EventResponse, responses=ERRORS)
def impression(
    body: EventRequest, request: Request, session: SessionDependency, clock: ClockDependency
) -> EventResponse:
    return accept_event(body, request, session, "impression", clock)


@router.post("/api/v1/events/click", response_model=EventResponse, responses=ERRORS)
def click(
    body: EventRequest, request: Request, session: SessionDependency, clock: ClockDependency
) -> EventResponse:
    return accept_event(body, request, session, "click", clock)


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready", responses={503: {"model": ErrorResponse}})
def ready(database: Annotated[Database, Depends(get_database)]) -> dict[str, str]:
    try:
        with stage("database_probe_ms"), database.session() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise WorkflowError(503, "database_unavailable", "Database is unavailable") from None
    return {"status": "ready"}
