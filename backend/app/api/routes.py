from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_clock,
    get_ctr_model,
    get_database,
    get_profile_cache,
    get_ranking_strategy,
    get_session,
    get_settings,
)
from app.cache.profiles import RedisProfileCache
from app.core.errors import WorkflowError
from app.core.observability import stage
from app.ctr.serving import CTRModel
from app.db.session import Database
from app.experiments.management import create_experiment, list_experiments, transition_experiment
from app.experiments.results import experiment_results
from app.ranking.strategies import RankingStrategy
from app.schemas.analytics import AnalyticsOverviewResponse, MetricsResponse
from app.schemas.experiments import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResultsResponse,
)
from app.schemas.lifecycle import (
    ErrorResponse,
    EventRequest,
    EventResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.analytics import analytics_overview, metrics_summary, runtime_capabilities
from app.services.events import EventType, record_event
from app.services.recommendations import recommend

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_session)]
ClockDependency = Annotated[Callable[[], datetime], Depends(get_clock)]
CTRDependency = Annotated[CTRModel, Depends(get_ctr_model)]
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
    strategy: Annotated[RankingStrategy, Depends(get_ranking_strategy)],
    model: CTRDependency,
    profile_cache: Annotated[RedisProfileCache, Depends(get_profile_cache)],
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
            strategy=strategy,
            ctr_model=model,
            profile_cache=profile_cache,
            request_context=request.state.context,
        )
    request.state.context.update(
        experiment_id=str(result.experiment_id) if result.experiment_id else None,
        experiment_variant=result.experiment_variant,
        outcome=(
            "replay"
            if result.replayed
            else "no_ad"
            if result.recommendation_id is None
            else "selection"
        ),
    )
    retrieval = result.retrieval or (
        result.selection.retrieval if result.selection is not None else None
    )
    if retrieval is not None:
        request.state.context.update(
            retrieval_mode=retrieval.mode,
            fallback_reason=retrieval.fallback_reason,
        )
    if result.recommendation_id is None:
        return Response(status_code=204)
    assert result.selection is not None
    request.state.context.update(
        recommendation_id=str(result.recommendation_id),
        ad_id=result.selection.id,
        strategy=result.selection.strategy,
        score=result.selection.model_dump(mode="json")["score"],
        score_meaning=result.selection.score_meaning,
        strategy_version=result.selection.strategy_version,
        model_id=result.selection.model_id,
        model_version=result.selection.model_version,
        feature_version=result.selection.feature_version,
        outcome=request.state.context["outcome"],
    )
    return RecommendationResponse(
        recommendation_id=result.recommendation_id,
        user_id=result.user_id,
        created_at=result.created_at,
        replayed=result.replayed,
        experiment_id=result.experiment_id,
        experiment_variant=result.experiment_variant,
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
    request.state.context.update(
        experiment_id=(str(result.experiment_id) if result.experiment_id else None),
        experiment_variant=result.experiment_variant,
    )
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


@router.get("/api/v1/analytics/overview", response_model=AnalyticsOverviewResponse)
def analytics_overview_route(
    session: SessionDependency, clock: ClockDependency
) -> AnalyticsOverviewResponse:
    return analytics_overview(session, as_of=clock())


@router.get("/api/v1/metrics", response_model=MetricsResponse)
def metrics_route(
    request: Request,
    clock: ClockDependency,
    profile_cache: Annotated[RedisProfileCache, Depends(get_profile_cache)],
    model: CTRDependency,
) -> MetricsResponse:
    as_of = clock()
    return metrics_summary(
        as_of=as_of,
        telemetry=request.app.state.telemetry.snapshot(now=as_of),
        profile_cache=profile_cache,
        snapshots=request.app.state.snapshots,
        model=model,
    )


@router.get("/health/ready", responses={503: {"model": ErrorResponse}})
def ready(
    request: Request,
    database: Annotated[Database, Depends(get_database)],
    profile_cache: Annotated[RedisProfileCache, Depends(get_profile_cache)],
) -> dict[str, Any]:
    try:
        with stage("database_probe_ms"), database.session() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise WorkflowError(503, "database_unavailable", "Database is unavailable") from None
    cache_status = profile_cache.health()
    capabilities = runtime_capabilities(request.app.state.snapshots, request.app.state.ctr_model)
    return {
        "status": "ready",
        "dependencies": {
            "database": "ready",
            "redis": cache_status,
        },
        "profile_cache": profile_cache.metrics.snapshot(),
        "capabilities": capabilities.model_dump(),
    }


@router.post("/api/v1/experiments", response_model=ExperimentResponse, status_code=201)
def create_experiment_route(
    body: ExperimentCreate, session: SessionDependency, model: CTRDependency
) -> ExperimentResponse:
    return ExperimentResponse.model_validate(
        create_experiment(session, body, model), from_attributes=True
    )


@router.get("/api/v1/experiments", response_model=list[ExperimentResponse])
def list_experiments_route(session: SessionDependency) -> list[ExperimentResponse]:
    return [
        ExperimentResponse.model_validate(record, from_attributes=True)
        for record in list_experiments(session)
    ]


@router.post(
    "/api/v1/experiments/{experiment_id}/start", response_model=ExperimentResponse, responses=ERRORS
)
def start_experiment_route(
    experiment_id: str, session: SessionDependency, model: CTRDependency
) -> ExperimentResponse:
    from uuid import UUID

    try:
        identity = UUID(experiment_id)
    except ValueError:
        raise WorkflowError(404, "experiment_not_found", "Experiment was not found") from None
    record = transition_experiment(session, identity, "start", model)
    return ExperimentResponse.model_validate(record, from_attributes=True)


@router.post(
    "/api/v1/experiments/{experiment_id}/stop", response_model=ExperimentResponse, responses=ERRORS
)
def stop_experiment_route(
    experiment_id: str, session: SessionDependency, model: CTRDependency
) -> ExperimentResponse:
    from uuid import UUID

    try:
        identity = UUID(experiment_id)
    except ValueError:
        raise WorkflowError(404, "experiment_not_found", "Experiment was not found") from None
    record = transition_experiment(session, identity, "stop", model)
    return ExperimentResponse.model_validate(record, from_attributes=True)


@router.get(
    "/api/v1/experiments/{experiment_id}/results",
    response_model=ExperimentResultsResponse,
    responses=ERRORS,
)
def experiment_results_route(
    experiment_id: UUID,
    request: Request,
    session: SessionDependency,
    clock: ClockDependency,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ExperimentResultsResponse:
    as_of = clock()
    return ExperimentResultsResponse.model_validate(
        experiment_results(
            session,
            experiment_id,
            start_at=start_at,
            end_at=end_at,
            as_of=as_of,
            telemetry=request.app.state.telemetry.snapshot(now=as_of),
        )
    )
