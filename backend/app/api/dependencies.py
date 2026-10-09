"""Synchronous dependencies scoped to the application serving each request."""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.config import Settings
from app.ctr.serving import CTRModel
from app.db.session import Database


def get_ctr_model(request: Request) -> CTRModel:
    return cast(CTRModel, request.app.state.ctr_model)


def get_clock() -> Callable[[], datetime]:
    """Server-owned clock; tests can override time without accepting client timestamps."""
    return utc_now


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


def get_session(request: Request) -> Iterator[Session]:
    """Services commit before responding; teardown only closes/rolls back."""
    with get_database(request).session() as session:
        yield session
