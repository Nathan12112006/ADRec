"""Uvicorn factory entry point; importing this module needs no environment or database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.routes import router
from app.cache.profiles import RedisProfileCache, create_profile_cache
from app.core.config import Settings, load_settings
from app.core.errors import WorkflowError
from app.core.observability import RollingTelemetry, configure_logging, logger, stages
from app.ctr.serving import CTRModel, CTRUnavailable
from app.db.session import Database
from app.retrieval.snapshots import ActiveSnapshot, SnapshotLoadError


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else load_settings()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(config)
        profile_cache = create_profile_cache(config)
        app.state.database = database
        app.state.profile_cache = profile_cache
        try:
            app.state.ctr_model = CTRModel.unavailable()
            if config.ctr_model_path is not None:
                try:
                    app.state.ctr_model = CTRModel.load(config.ctr_model_path)
                except CTRUnavailable:
                    logger.warning(
                        "CTR model unavailable; baseline serving remains available",
                        extra={"request_context": {"event": "ctr_unavailable"}},
                    )
            if config.retrieval_index_path is not None:
                try:
                    app.state.snapshots.reload(config.retrieval_index_path)
                except SnapshotLoadError:
                    # The retriever exposes the failure and uses current exact inventory.
                    pass
            yield
        finally:
            profile_cache.close()
            database.dispose()

    app = FastAPI(title="AdFlow", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    app.state.snapshots = ActiveSnapshot()
    app.state.ctr_model = CTRModel.unavailable()
    app.state.telemetry = RollingTelemetry()
    app.state.profile_cache = RedisProfileCache(None)

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        request.state.context["error_code"] = code
        return JSONResponse(
            status_code=status, content={"error": {"code": code, "message": message}}
        )

    @app.exception_handler(WorkflowError)
    async def workflow_error(request: Request, error: WorkflowError) -> JSONResponse:
        return error_response(request, error.status_code, error.code, str(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Do not echo inputs, request bodies or validation exception strings.
        return error_response(request, 422, "invalid_request", "Request validation failed")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return error_response(request, 503, "database_unavailable", "Database is unavailable")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return error_response(request, error.status_code, "http_error", "HTTP request failed")

    @app.middleware("http")
    async def request_logging(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = perf_counter()
        request_id = str(uuid4())
        request.state.context = {"request_id": request_id}
        timings: dict[str, float] = {}
        token = stages.set(timings)
        try:
            try:
                response = await call_next(request)
            except Exception:
                response = error_response(request, 500, "internal_error", "Internal server error")
            response.headers["X-Request-ID"] = request_id
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            context = request.state.context
            if response.status_code >= 400:
                population = "error"
            elif route_path == "/api/v1/recommendations":
                population = context.get("outcome", "other")
            elif route_path == "/api/v1/events/impression":
                population = "impression"
            elif route_path == "/api/v1/events/click":
                population = "click"
            else:
                population = "other"
            experiment_id = context.get("experiment_id")
            variant = context.get("experiment_variant")
            attribution = (
                "assigned"
                if experiment_id is not None and variant is not None
                else "unknown"
                if route_path == "/api/v1/recommendations" and response.status_code >= 400
                else "outside_experiment"
                if route_path == "/api/v1/recommendations"
                else None
            )
            duration_ms = (perf_counter() - started) * 1000
            app.state.telemetry.record(
                route=route_path,
                method=request.method,
                status=response.status_code,
                duration_ms=duration_ms,
                population=population,
                experiment_id=experiment_id,
                variant=variant,
                attribution=attribution,
                error_code=context.get("error_code"),
                retrieval_mode=context.get("retrieval_mode"),
                fallback_reason=context.get("fallback_reason"),
                stages=timings,
            )
            logger.info(
                "request",
                extra={
                    "request_context": {
                        **request.state.context,
                        "method": request.method,
                        "route": route_path,
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                        "stages": timings,
                    }
                },
            )
            return response
        finally:
            stages.reset(token)

    app.include_router(router)
    return app
