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
from app.core.config import Settings, load_settings
from app.core.errors import WorkflowError
from app.core.observability import configure_logging, logger, stages
from app.ctr.serving import CTRModel, CTRUnavailable
from app.db.session import Database
from app.retrieval.snapshots import ActiveSnapshot, SnapshotLoadError


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else load_settings()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(config)
        app.state.database = database
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
            database.dispose()

    app = FastAPI(title="AdFlow", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    app.state.snapshots = ActiveSnapshot()
    app.state.ctr_model = CTRModel.unavailable()

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
            logger.info(
                "request",
                extra={
                    "request_context": {
                        **request.state.context,
                        "method": request.method,
                        "route": getattr(route, "path", "unmatched"),
                        "status": response.status_code,
                        "duration_ms": (perf_counter() - started) * 1000,
                        "stages": timings,
                    }
                },
            )
            return response
        finally:
            stages.reset(token)

    app.include_router(router)
    return app
