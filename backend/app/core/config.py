"""Validated environment settings; database secrets never appear in diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import unquote

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.retrieval.limits import DEFAULT_CANDIDATE_LIMIT, MAX_CANDIDATE_LIMIT, MAX_SEARCH_LIMIT

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class ConfigurationError(ValueError):
    """Safe startup diagnostic containing field names and error codes only."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADFLOW_", extra="forbid", hide_input_in_errors=True, frozen=True
    )

    database_url: SecretStr
    test_database_url: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_pool_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_statement_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_lock_timeout_seconds: int = Field(default=3, ge=1, le=30)
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=5, ge=0, le=20)
    retrieval_candidate_limit: int = Field(
        default=DEFAULT_CANDIDATE_LIMIT, ge=1, le=MAX_CANDIDATE_LIMIT
    )
    retrieval_search_limit: int = Field(default=4000, ge=1, le=MAX_SEARCH_LIMIT)

    @model_validator(mode="after")
    def validate_retrieval_limits(self) -> Settings:
        if self.retrieval_search_limit < self.retrieval_candidate_limit:
            raise ValueError("retrieval search limit must cover the candidate limit")
        return self

    @field_validator("database_url", "test_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host)
                and bool(url.database)
                and (url.port is None or 1 <= url.port <= 65535)
                and not url.query
            )
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError("use a PostgreSQL psycopg URL with host/database and no query options")
        return value

    @model_validator(mode="after")
    def validate_database_isolation(self) -> Settings:
        app_database = make_url(self.database_url.get_secret_value()).database or ""
        test_database = make_url(self.test_database_url.get_secret_value()).database or ""
        if unquote(app_database) == unquote(test_database):
            raise ValueError("application and test settings require distinct database names")
        return self


def load_settings(*, env_file: Path | None = DEFAULT_ENV_FILE) -> Settings:
    """Load once per app instance; environment variables override the root .env."""
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        fields = ", ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['type']}" for item in error.errors()
        )
        raise ConfigurationError(f"Invalid AdFlow configuration ({fields})") from None
    except SettingsError:
        raise ConfigurationError("Unable to read AdFlow configuration") from None
