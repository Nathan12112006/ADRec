"""Synchronous dependencies scoped to the application serving each request."""

from typing import cast

from fastapi import Request

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)
