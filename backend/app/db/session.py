"""Lazy, bounded PostgreSQL connections; callers own transaction boundaries."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings, *, use_test_database: bool = False) -> None:
        url = settings.test_database_url if use_test_database else settings.database_url
        self.engine = create_engine(
            url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            hide_parameters=True,
            connect_args={
                "connect_timeout": settings.db_connect_timeout_seconds,
                "options": (
                    "-c timezone=UTC "
                    f"-c statement_timeout={settings.db_statement_timeout_seconds * 1000} "
                    f"-c lock_timeout={settings.db_lock_timeout_seconds * 1000} "
                    "-c idle_in_transaction_session_timeout=30000"
                ),
            },
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Close and roll back uncommitted work; never commit during HTTP teardown."""
        with self._sessions() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit on success, roll back on any exception, always release the connection."""
        with self._sessions.begin() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
