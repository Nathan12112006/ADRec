import socket
import threading
import time
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, TimeoutError

from app.core.config import Settings
from app.db.session import Database


@pytest.fixture
def bounded_database(database_settings: Settings) -> Iterator[Database]:
    settings = database_settings.model_copy(
        update={
            "db_pool_size": 1,
            "db_max_overflow": 0,
            "db_pool_timeout_seconds": 1,
            "db_statement_timeout_seconds": 3,
            "db_lock_timeout_seconds": 1,
        }
    )
    database = Database(settings, use_test_database=True)
    yield database
    database.dispose()


def test_statement_timeout_cancels_query_and_pool_recovers(bounded_database: Database) -> None:
    started = time.monotonic()
    with pytest.raises(OperationalError):
        with bounded_database.transaction() as session:
            session.execute(text("SELECT pg_sleep(20)"))
    assert time.monotonic() - started < 8
    with bounded_database.transaction() as session:
        assert session.scalar(text("SELECT 1")) == 1


def test_pool_exhaustion_has_a_bounded_wait(bounded_database: Database) -> None:
    with bounded_database.session() as first:
        first.execute(text("SELECT 1"))
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            with bounded_database.transaction() as second:
                second.execute(text("SELECT 1"))
        assert time.monotonic() - started < 5
    with bounded_database.transaction() as session:
        assert session.scalar(text("SELECT 1")) == 1


def test_lock_timeout_cancels_wait_and_transaction_recovers(
    database: Database, bounded_database: Database
) -> None:
    with database.transaction() as owner:
        owner.execute(text("SELECT pg_advisory_xact_lock(2026100702)"))
        started = time.monotonic()
        with pytest.raises(OperationalError):
            with bounded_database.transaction() as waiter:
                waiter.execute(text("SELECT pg_advisory_xact_lock(2026100702)"))
        assert time.monotonic() - started < 5
    with bounded_database.transaction() as session:
        assert session.scalar(text("SELECT 1")) == 1


def test_connection_handshake_timeout_is_bounded(database_settings: Settings) -> None:
    # Accept TCP without answering PostgreSQL: a refused port would not prove the timeout.
    finished = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(8)

        def stall_handshake() -> None:
            with listener.accept()[0]:
                finished.wait(8)

        worker = threading.Thread(target=stall_handshake)
        worker.start()
        port = listener.getsockname()[1]
        settings = Settings(
            database_url=database_settings.database_url,
            test_database_url=f"postgresql+psycopg://adflow@127.0.0.1:{port}/handshake_test",
            db_connect_timeout_seconds=1,
        )
        database = Database(settings, use_test_database=True)
        try:
            started = time.monotonic()
            with pytest.raises(OperationalError):
                with database.transaction() as session:
                    session.execute(text("SELECT 1"))
            assert time.monotonic() - started < 6
        finally:
            finished.set()
            worker.join(timeout=10)
            database.dispose()
