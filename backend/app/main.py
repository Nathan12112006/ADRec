"""Uvicorn factory entry point; importing this module needs no environment or database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, load_settings
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(config)
        app.state.database = database
        try:
            yield
        finally:
            database.dispose()

    app = FastAPI(title="AdFlow", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    return app
