from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg.errors import ForeignKeyViolation
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset, Event, Recommendation, RequestOutcome, User


def test_migration_creates_schema_and_transaction_commits(database: Database) -> None:
    dataset_id = uuid4()
    with database.transaction() as session:
        session.execute(
            text(
                "INSERT INTO datasets (id, seed, generator_version, configuration) "
                "VALUES (:id, 42, 'test-v1', '{}'::jsonb)"
            ),
            {"id": dataset_id},
        )
    with database.transaction() as session:
        assert (
            session.scalar(
                text("SELECT generator_version FROM datasets WHERE id = :id"), {"id": dataset_id}
            )
            == "test-v1"
        )


def test_request_keys_are_unique_in_postgresql(database: Database) -> None:
    dataset_id = uuid4()
    request_key = str(uuid4())
    with database.transaction() as session:
        session.execute(
            text(
                "INSERT INTO datasets (id, seed, generator_version, configuration) "
                "VALUES (:id, 42, 'test-v1', '{}'::jsonb)"
            ),
            {"id": dataset_id},
        )
        user_id = session.scalar(
            text(
                "INSERT INTO users (dataset_id, interests, category_preferences, age_group, "
                "country, device) VALUES (:id, '{}', '{}', '25-34', 'US', 'mobile') RETURNING id"
            ),
            {"id": dataset_id},
        )
        session.execute(
            text("INSERT INTO request_outcomes (request_key, user_id) VALUES (:key, :user)"),
            {"key": request_key, "user": user_id},
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("INSERT INTO request_outcomes (request_key, user_id) VALUES (:key, :user)"),
                {"key": request_key, "user": user_id},
            )


@pytest.fixture
def selection(database: Database) -> Recommendation:
    with database.transaction() as session:
        dataset = Dataset(seed=42, generator_version="test-v1", configuration={})
        session.add(dataset)
        session.flush()
        user = User(
            dataset_id=dataset.id,
            interests=["sports"],
            category_preferences=[],
            age_group="25-34",
            country="US",
            device="mobile",
        )
        advertiser = Advertiser(dataset_id=dataset.id, name="Synthetic advertiser")
        session.add_all([user, advertiser])
        session.flush()
        ad = Ad(
            dataset_id=dataset.id,
            advertiser_id=advertiser.id,
            title="Original title",
            description="Synthetic ad",
            target_url="https://example.test/ad",
            category="sports",
            interests=["sports"],
            bid=Decimal("1.2500"),
        )
        session.add(ad)
        session.flush()
        recommendation = Recommendation(
            dataset_id=dataset.id,
            user_id=user.id,
            ad_id=ad.id,
            bid=ad.bid,
            selected_ad={
                "title": ad.title,
                "description": ad.description,
                "target_url": ad.target_url,
                "category": ad.category,
                "interests": ad.interests,
                "advertiser_id": ad.advertiser_id,
            },
        )
        session.add(recommendation)
        session.flush()
        session.add(
            RequestOutcome(
                request_key=str(uuid4()), user_id=user.id, recommendation_id=recommendation.id
            )
        )
    return recommendation


def test_selection_snapshot_cannot_be_rewritten(
    database: Database, selection: Recommendation
) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text("UPDATE recommendations SET bid = 999 WHERE id = :id"), {"id": selection.id}
            )


def test_snapshots_survive_ad_changes_with_decimal_money_and_utc_time(
    database: Database, selection: Recommendation
) -> None:
    with database.transaction() as session:
        session.execute(
            text("UPDATE ads SET bid = 9, title = 'Changed', active = false WHERE id = :id"),
            {"id": selection.ad_id},
        )
    with database.transaction() as session:
        saved = session.get(Recommendation, selection.id)
        assert saved is not None
        assert saved.bid == Decimal("1.2500")
        assert saved.selected_ad["title"] == "Original title"
        offset = saved.created_at.utcoffset()
        assert offset is not None and offset.total_seconds() == 0


def test_each_event_type_is_counted_once_including_revenue(
    database: Database, selection: Recommendation
) -> None:
    with database.transaction() as session:
        session.add_all(
            [
                Event(recommendation_id=selection.id, event_type="impression"),
                Event(
                    recommendation_id=selection.id,
                    event_type="click",
                    simulated_revenue=Decimal("1.2500"),
                ),
            ]
        )
    for event_type in ["impression", "click"]:
        with pytest.raises(IntegrityError):
            with database.transaction() as session:
                session.add(Event(recommendation_id=selection.id, event_type=event_type))
    with database.transaction() as session:
        events = session.scalars(select(Event).where(Event.recommendation_id == selection.id)).all()
        assert len(events) == 2
        assert sum(event.simulated_revenue for event in events) == Decimal("1.2500")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO events (recommendation_id, event_type) VALUES (:missing_id, 'click')",
        "INSERT INTO events (recommendation_id, event_type) VALUES (:id, 'conversion')",
        "INSERT INTO events (recommendation_id, event_type, simulated_revenue) "
        "VALUES (:id, 'impression', 1)",
        "INSERT INTO events (recommendation_id, event_type, simulated_revenue) "
        "VALUES (:id, 'click', -1)",
        "INSERT INTO events (recommendation_id, event_type, simulated_revenue) "
        "VALUES (:id, 'click', 'NaN')",
        "INSERT INTO request_outcomes (request_key, user_id) VALUES (:key, -1)",
        "INSERT INTO request_outcomes (request_key, user_id, recommendation_id) "
        "VALUES (:key, :user_id, :missing_id)",
        "UPDATE ads SET advertiser_id = -1 WHERE id = :ad_id",
        "UPDATE ads SET bid = -1 WHERE id = :ad_id",
        "UPDATE ads SET bid = 'NaN' WHERE id = :ad_id",
    ],
)
def test_constraints_reject_invalid_raw_writes(
    database: Database, selection: Recommendation, sql: str
) -> None:
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(sql),
                {
                    "missing_id": uuid4(),
                    "id": selection.id,
                    "key": str(uuid4()),
                    "user_id": selection.user_id,
                    "ad_id": selection.ad_id,
                },
            )


def test_cross_dataset_and_cross_user_references_are_rejected(
    database: Database, selection: Recommendation
) -> None:
    with database.transaction() as session:
        dataset = Dataset(seed=17, generator_version="test-v1", configuration={})
        session.add(dataset)
        session.flush()
        user = User(
            dataset_id=dataset.id,
            interests=[],
            category_preferences=[],
            age_group="25-34",
            country="US",
            device="mobile",
        )
        session.add(user)
        session.flush()
        unattached = Recommendation(
            dataset_id=selection.dataset_id,
            user_id=selection.user_id,
            ad_id=selection.ad_id,
            bid=selection.bid,
            selected_ad=selection.selected_ad,
        )
        session.add(unattached)
        session.flush()
    for sql in [
        "INSERT INTO request_outcomes (request_key, user_id, recommendation_id) "
        "VALUES (:key, :other_user, :id)",
        "INSERT INTO recommendations (id, dataset_id, user_id, ad_id, bid, selected_ad) "
        "VALUES (:new_id, :dataset, :other_user, :ad_id, 1, '{}'::jsonb)",
        "UPDATE ads SET dataset_id = :dataset WHERE id = :ad_id",
    ]:
        with pytest.raises(IntegrityError) as error:
            with database.transaction() as session:
                session.execute(
                    text(sql),
                    {
                        "key": str(uuid4()),
                        "other_user": user.id,
                        "id": unattached.id,
                        "new_id": uuid4(),
                        "dataset": dataset.id,
                        "ad_id": selection.ad_id,
                    },
                )
        assert isinstance(error.value.orig, ForeignKeyViolation)


@pytest.mark.parametrize("table", ["datasets", "recommendations", "request_outcomes", "events"])
def test_durable_history_cannot_be_deleted_or_truncated(
    database: Database, selection: Recommendation, table: str
) -> None:
    with database.transaction() as session:
        session.add(Event(recommendation_id=selection.id, event_type="impression"))
    for sql in [f"DELETE FROM {table}", f"TRUNCATE {table} CASCADE"]:
        with pytest.raises(IntegrityError):
            with database.transaction() as session:
                session.execute(text(sql))


def test_failed_write_rolls_back_all_work_and_next_transaction_succeeds(
    database: Database, selection: Recommendation
) -> None:
    dataset_id = uuid4()
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                Dataset(id=dataset_id, seed=99, generator_version="rollback", configuration={})
            )
            session.flush()
            session.add(Event(recommendation_id=selection.id, event_type="invalid"))
    with database.transaction() as session:
        assert session.get(Dataset, dataset_id) is None
        assert session.scalar(text("SELECT 1")) == 1


def test_session_cleanup_does_not_commit_unfinished_work(database: Database) -> None:
    dataset_id = uuid4()
    with database.session() as session:
        session.add(
            Dataset(id=dataset_id, seed=99, generator_version="uncommitted", configuration={})
        )
        session.flush()
    with database.transaction() as session:
        assert session.get(Dataset, dataset_id) is None


def test_no_ad_outcome_has_no_recommendation(database: Database, selection: Recommendation) -> None:
    key = str(uuid4())
    with database.transaction() as session:
        session.add(RequestOutcome(request_key=key, user_id=selection.user_id))
    with database.transaction() as session:
        outcome = session.get(RequestOutcome, key)
        assert outcome is not None and outcome.recommendation_id is None


@pytest.mark.parametrize("table", ["recommendations", "request_outcomes", "events"])
def test_history_timestamps_cannot_be_rewritten(
    database: Database, selection: Recommendation, table: str
) -> None:
    with database.transaction() as session:
        session.add(Event(recommendation_id=selection.id, event_type="impression"))
    column = "id" if table == "recommendations" else "recommendation_id"
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(f"UPDATE {table} SET created_at = now() WHERE {column} = :id"),
                {"id": selection.id},
            )
