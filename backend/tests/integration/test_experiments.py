from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from psycopg.errors import UniqueViolation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import Database
from app.experiments.assignment import AssignmentConfig, assign_variant
from app.models.records import Experiment


def test_migrated_experiment_preserves_assignment_and_started_treatment(database: Database) -> None:
    experiment_id = uuid4()
    with database.transaction() as session:
        record = Experiment(id=experiment_id, name="Synthetic comparison", model_id="a" * 64)
        session.add(record)
        session.flush()
        config = AssignmentConfig.model_validate(record)
        assert record.status == "draft" and record.schema_version == "ranking-experiment-v1"
        assert record.control_strategy_version == "baseline-v1"
        assert record.treatment_strategy_version == "expected-value-v1"
        assert (
            record.model_version == "ctr-logistic-v1"
            and record.feature_version == "ctr-features-v1"
        )
        assert record.retrieval_mode == "exact" and record.candidate_limit == 500
        assert record.search_limit == 4000 and record.hnsw_ef_search is None
    with database.transaction() as session:
        saved = session.get(Experiment, experiment_id)
        assert saved is not None
        assert AssignmentConfig.model_validate(saved) == config
        assert assign_variant(42, AssignmentConfig.model_validate(saved)) == assign_variant(
            42, config
        )
        session.execute(
            text(
                "UPDATE experiments SET status='running', started_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE experiments SET model_id=:model WHERE id=:id"),
                {"id": experiment_id, "model": "b" * 64},
            )
    with database.transaction() as session:
        session.execute(
            text(
                "UPDATE experiments SET status='stopped', stopped_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(text("DELETE FROM experiments WHERE id=:id"), {"id": experiment_id})
    with database.transaction() as session:
        stopped = session.get(Experiment, experiment_id)
        assert stopped is not None and stopped.status == "stopped"
        assert stopped.model_id == "a" * 64


@pytest.fixture
def experiment_id(database: Database) -> Iterator[UUID]:
    with database.transaction() as session:
        record = Experiment(name="Constraint example", model_id="a" * 64)
        session.add(record)
        session.flush()
        identity = record.id
    yield identity
    with database.transaction() as session:
        session.execute(
            text(
                "UPDATE experiments SET status='stopped', "
                "stopped_at=clock_timestamp() WHERE id=:id AND status='running'"
            ),
            {"id": identity},
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "control_basis_points=-1",
        "control_basis_points=10001",
        "name=' '",
        "model_id='bad'",
        "control_strategy='auction'",
        "model_version=''",
        "candidate_limit=0",
        "candidate_limit=501",
        "search_limit=1",
        "search_limit=1000001",
        "retrieval_mode='unknown'",
        "hnsw_ef_search=64",
        "retrieval_mode='hnsw'",
        "retrieval_mode='hnsw', hnsw_ef_search=0",
        "status='running'",
        "status='stopped', started_at=clock_timestamp(), stopped_at=clock_timestamp()",
    ],
)
def test_schema_rejects_invalid_draft_configuration(
    database: Database, experiment_id: UUID, mutation: str
) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(f"UPDATE experiments SET {mutation} WHERE id=:id"), {"id": experiment_id}
            )


@pytest.mark.parametrize(
    "mutation",
    [
        "id='00000000-0000-0000-0000-000000000001'",
        "salt=repeat('b',64)",
        "assignment_version='new'",
        "schema_version='new'",
        "created_at=created_at + interval '1 second'",
    ],
)
def test_assignment_identity_is_immutable_even_in_draft(
    database: Database, experiment_id: UUID, mutation: str
) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(f"UPDATE experiments SET {mutation} WHERE id=:id"), {"id": experiment_id}
            )


@pytest.mark.parametrize(
    "mutation",
    [
        "control_basis_points=0",
        "control_strategy='expected-value'",
        "treatment_strategy='interest-overlap'",
        "control_strategy_version='new'",
        "treatment_strategy_version='new'",
        "model_id=repeat('b',64)",
        "model_version='new'",
        "feature_version='new'",
        "candidate_limit=1",
        "search_limit=500",
        "retrieval_mode='hnsw', hnsw_ef_search=64",
        "vector_version='new'",
        "vocabulary_version='new'",
        "name='Renamed'",
        "started_at=started_at + interval '1 second'",
        "status='draft', started_at=NULL",
        "status='stopped', stopped_at=clock_timestamp(), control_basis_points=0",
    ],
)
def test_started_treatment_cannot_change_even_in_stop_transaction(
    database: Database, experiment_id: UUID, mutation: str
) -> None:
    with database.transaction() as session:
        session.execute(
            text(
                "UPDATE experiments SET status='running', started_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(f"UPDATE experiments SET {mutation} WHERE id=:id"), {"id": experiment_id}
            )


def test_draft_edits_freeze_at_start_and_stopped_experiment_cannot_resume(
    database: Database, experiment_id: UUID
) -> None:
    with database.transaction() as session:
        session.execute(
            text(
                "UPDATE experiments SET control_basis_points=2500, "
                "retrieval_mode='hnsw', hnsw_ef_search=64, candidate_limit=50 WHERE "
                "id=:id"
            ),
            {"id": experiment_id},
        )
        session.execute(
            text(
                "UPDATE experiments SET status='running', started_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
    with database.transaction() as session:
        session.execute(
            text(
                "UPDATE experiments SET status='stopped', stopped_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": experiment_id},
        )
    for mutation in ("status='running', stopped_at=NULL", "name='Changed'"):
        with pytest.raises(IntegrityError):
            with database.transaction() as session:
                session.execute(
                    text(f"UPDATE experiments SET {mutation} WHERE id=:id"), {"id": experiment_id}
                )
    with database.transaction() as session:
        saved = session.get(Experiment, experiment_id)
        assert saved is not None and saved.control_basis_points == 2500
        assert saved.retrieval_mode == "hnsw" and saved.hnsw_ef_search == 64


def test_truncation_cannot_remove_experiment_history(
    database: Database, experiment_id: UUID
) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(text("TRUNCATE experiments"))
    with database.transaction() as session:
        assert session.get(Experiment, experiment_id) is not None


def test_concurrent_starts_have_one_winner_and_stopping_allows_a_new_experiment(
    database: Database,
) -> None:
    with database.transaction() as session:
        records = [Experiment(name="Concurrent example", model_id="a" * 64) for _ in range(2)]
        session.add_all(records)
        session.flush()
        identities = [record.id for record in records]
    ready = Barrier(2)

    def start(identity: UUID) -> UUID | None:
        try:
            with database.transaction() as session:
                ready.wait(timeout=10)
                session.execute(
                    text(
                        "UPDATE experiments SET status='running', "
                        "started_at=clock_timestamp() WHERE id=:id"
                    ),
                    {"id": identity},
                )
            return identity
        except IntegrityError as error:
            assert isinstance(error.orig, UniqueViolation)
            assert error.orig.diag.constraint_name == "one_running_ranking_experiment"
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, identities))
        winners = [outcome for outcome in outcomes if outcome is not None]
        assert len(winners) == 1
        winner = winners[0]
        loser = next(identity for identity in identities if identity != winner)
        with database.transaction() as session:
            session.execute(
                text(
                    "UPDATE experiments SET status='stopped', "
                    "stopped_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": winner},
            )
            session.execute(
                text(
                    "UPDATE experiments SET status='running', "
                    "started_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": loser},
            )
        with database.transaction() as session:
            saved_winner, saved_loser = (
                session.get(Experiment, winner),
                session.get(Experiment, loser),
            )
            assert saved_winner is not None and saved_winner.status == "stopped"
            assert saved_loser is not None and saved_loser.status == "running"
    finally:
        with database.transaction() as session:
            for identity in identities:
                session.execute(
                    text(
                        "UPDATE experiments SET status='stopped', "
                        "stopped_at=clock_timestamp() WHERE id=:id AND "
                        "status='running'"
                    ),
                    {"id": identity},
                )
