"""Uvicorn factory entry point; importing this module needs no environment or database."""

from fastapi import FastAPI

from app.core.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else load_settings()
    app = FastAPI(title="AdFlow", version="0.1.0")
    app.state.settings = config
    return app
