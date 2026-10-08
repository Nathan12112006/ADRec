"""Explicitly opt in to PostgreSQL tests; never reset a configured database."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import Settings, load_settings
from app.db.session import Database


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    if os.environ.get("ADFLOW_RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set ADFLOW_RUN_POSTGRES_TESTS=1 to use the isolated PostgreSQL test database")
    return load_settings()


@pytest.fixture(scope="session")
def database(database_settings: Settings) -> Iterator[Database]:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["settings"] = database_settings
    config.attributes["use_test_database"] = True
    command.upgrade(config, "head")
    db = Database(database_settings, use_test_database=True)
    yield db
    db.dispose()
