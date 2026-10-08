from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.errors import WorkflowError
from app.db.session import Database
from app.models.records import Ad, Advertiser, Event
from app.seeding import SeedConfig, generate_entities, seed_database
from app.services.events import EventResult, EventType, record_event
from app.services.recommendations import RecommendationResult, recommend

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def opportunity(database: Database, request: pytest.FixtureRequest) -> RecommendationResult:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=1)
    seed_database(database, config, append=True)
    user_id = next(row["id"] for kind, row in generate_entities(config) if kind == "users")
    with database.transaction() as session:
        session.execute(
            update(Ad)
            .where(Ad.dataset_id == config.dataset_id)
            .values(bid=getattr(request, "param", Decimal("1.25")))
        )
    with database.session() as session:
        return recommend(session, user_id, str(uuid4()), clock=lambda: NOW)


def test_display_confirmation_commits_impression_with_server_attribution(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None and opportunity.selection is not None
    with database.session() as session:
        result = record_event(
            session,
            opportunity.recommendation_id,
            "impression",
            clock=lambda: NOW + timedelta(minutes=1),
        )
        assert not session.in_transaction()
    assert result.recommendation_id == opportunity.recommendation_id
    assert result.event_type == "impression"
    assert result.user_id == opportunity.user_id
    assert result.ad_id == opportunity.selection.id
    assert result.created_at == NOW + timedelta(minutes=1)
    assert result.simulated_revenue == Decimal("0")


def test_first_click_requires_impression_and_can_recover_by_retry(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None
    with database.session() as session:
        with pytest.raises(WorkflowError) as error:
            record_event(session, opportunity.recommendation_id, "click", clock=lambda: NOW)
        assert error.value.status_code == 409
        assert error.value.code == "impression_required"
        record_event(session, opportunity.recommendation_id, "impression", clock=lambda: NOW)
        accepted = record_event(session, opportunity.recommendation_id, "click", clock=lambda: NOW)
        assert not session.in_transaction()
    assert accepted.simulated_revenue == Decimal("1.2500")


@pytest.mark.parametrize("event_type", ["impression", "click"])
def test_accepted_duplicates_replay_original_event_even_after_expiry(
    database: Database, opportunity: RecommendationResult, event_type: EventType
) -> None:
    assert opportunity.recommendation_id is not None
    with database.session() as session:
        if event_type == "click":
            record_event(session, opportunity.recommendation_id, "impression", clock=lambda: NOW)
        saved = record_event(session, opportunity.recommendation_id, event_type, clock=lambda: NOW)
        assert (
            record_event(
                session,
                opportunity.recommendation_id,
                event_type,
                clock=lambda: NOW + timedelta(minutes=5),
            )
            == saved
        )
        assert (
            record_event(
                session,
                opportunity.recommendation_id,
                event_type,
                clock=lambda: NOW + timedelta(days=2),
            )
            == saved
        )


@pytest.mark.parametrize("event_type", ["impression", "click"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_first_event_uses_strict_creation_based_expiration(
    database: Database, opportunity: RecommendationResult, event_type: EventType, offset: int
) -> None:
    assert opportunity.recommendation_id is not None
    received_at = NOW + timedelta(hours=24, microseconds=offset)
    with database.session() as session:
        if event_type == "click":
            record_event(session, opportunity.recommendation_id, "impression", clock=lambda: NOW)
        if offset < 0:
            result = record_event(
                session, opportunity.recommendation_id, event_type, clock=lambda: received_at
            )
            assert result.created_at == received_at
        else:
            with pytest.raises(WorkflowError) as error:
                record_event(
                    session, opportunity.recommendation_id, event_type, clock=lambda: received_at
                )
            assert error.value.status_code == 410
            assert error.value.code == "recommendation_expired"


@pytest.mark.parametrize("event_type", ["impression", "click"])
def test_unknown_recommendation_returns_404(database: Database, event_type: EventType) -> None:
    with database.session() as session:
        with pytest.raises(WorkflowError) as error:
            record_event(session, uuid4(), event_type)
        assert not session.in_transaction()
    assert error.value.status_code == 404


@pytest.mark.parametrize("event_type", ["impression", "click"])
def test_concurrent_duplicates_create_one_event_and_one_revenue_credit(
    database: Database, opportunity: RecommendationResult, event_type: EventType
) -> None:
    recommendation_id = opportunity.recommendation_id
    assert recommendation_id is not None
    if event_type == "click":
        with database.session() as session:
            record_event(session, recommendation_id, "impression", clock=lambda: NOW)
    start = Barrier(8)

    def request(index: int) -> EventResult:
        start.wait(timeout=10)
        with database.session() as session:
            return record_event(
                session,
                recommendation_id,
                event_type,
                clock=lambda: NOW + timedelta(seconds=index),
            )

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(request, range(8)))
    assert all(result == results[0] for result in results)
    with database.transaction() as session:
        count, revenue = session.execute(
            select(func.count(), func.sum(Event.simulated_revenue)).where(
                Event.recommendation_id == recommendation_id, Event.event_type == event_type
            )
        ).one()
    assert count == 1
    assert revenue == (Decimal("1.2500") if event_type == "click" else Decimal("0"))


def test_inventory_changes_do_not_change_event_attribution_or_captured_credit(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None and opportunity.selection is not None
    with database.transaction() as session:
        session.execute(
            update(Ad).where(Ad.id == opportunity.selection.id).values(bid=9, active=False)
        )
        session.execute(
            update(Advertiser)
            .where(Advertiser.id == opportunity.selection.advertiser_id)
            .values(active=False)
        )
    with database.session() as session:
        record_event(session, opportunity.recommendation_id, "impression", clock=lambda: NOW)
        result = record_event(session, opportunity.recommendation_id, "click", clock=lambda: NOW)
    assert result.ad_id == opportunity.selection.id
    assert result.user_id == opportunity.user_id
    assert result.simulated_revenue == Decimal("1.2500")


@pytest.mark.parametrize("event_type", ["impression", "click"])
@pytest.mark.parametrize("deferred", [False, True])
def test_failed_event_insert_or_commit_accepts_no_event_or_accounting_effect(
    database: Database, opportunity: RecommendationResult, event_type: EventType, deferred: bool
) -> None:
    recommendation_id = opportunity.recommendation_id
    assert recommendation_id is not None
    if event_type == "click":
        with database.session() as session:
            record_event(session, recommendation_id, "impression", clock=lambda: NOW)
    name = f"fail_ticket06_{uuid4().hex}"
    with database.transaction() as session:
        session.execute(
            text(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'Injected event failure'; END; $$"
            )
        )
        session.execute(
            text(
                f"CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON events "
                + ("DEFERRABLE INITIALLY DEFERRED " if deferred else "NOT DEFERRABLE ")
                + f"FOR EACH ROW WHEN (NEW.recommendation_id = '{recommendation_id}'::uuid "
                f"AND NEW.event_type = '{event_type}') EXECUTE FUNCTION {name}()"
            )
        )
    try:
        with database.session() as session:
            with pytest.raises(WorkflowError) as error:
                record_event(session, recommendation_id, event_type, clock=lambda: NOW)
            assert not session.in_transaction()
        assert error.value.status_code == 503
        assert "Injected" not in str(error.value)
        with database.transaction() as session:
            assert session.get(Event, (recommendation_id, event_type)) is None
            assert session.scalar(
                select(func.coalesce(func.sum(Event.simulated_revenue), 0)).where(
                    Event.recommendation_id == recommendation_id
                )
            ) == Decimal("0")
    finally:
        with database.transaction() as session:
            session.execute(text(f"DROP TRIGGER {name} ON events"))
            session.execute(text(f"DROP FUNCTION {name}()"))
    with database.session() as session:
        accepted = record_event(session, recommendation_id, event_type, clock=lambda: NOW)
    assert accepted.simulated_revenue == (
        Decimal("1.25") if event_type == "click" else Decimal("0")
    )


def test_event_database_unavailability_returns_safe_503(database_settings: Settings) -> None:
    url = make_url(database_settings.test_database_url.get_secret_value()).set(
        database=f"missing_ticket06_{uuid4().hex}"
    )
    unavailable = Database(
        Settings(
            database_url=database_settings.database_url,
            test_database_url=url.render_as_string(hide_password=False),
            db_connect_timeout_seconds=1,
        ),
        use_test_database=True,
    )
    try:
        with unavailable.session() as session:
            with pytest.raises(WorkflowError) as error:
                record_event(session, uuid4(), "impression")
            assert not session.in_transaction()
        assert error.value.status_code == 503
        assert "missing_ticket06" not in str(error.value)
    finally:
        unavailable.dispose()


@pytest.mark.parametrize("opportunity", [Decimal("0")], indirect=True)
def test_zero_captured_bid_accepts_click_with_zero_credit(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None
    with database.session() as session:
        record_event(session, opportunity.recommendation_id, "impression", clock=lambda: NOW)
        accepted = record_event(session, opportunity.recommendation_id, "click", clock=lambda: NOW)
        assert (
            record_event(
                session,
                opportunity.recommendation_id,
                "click",
                clock=lambda: NOW + timedelta(days=2),
            )
            == accepted
        )
    assert accepted.simulated_revenue == Decimal("0")


def test_expired_first_click_is_gone_even_when_impression_is_absent(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None
    with database.session() as session:
        with pytest.raises(WorkflowError) as error:
            record_event(
                session,
                opportunity.recommendation_id,
                "click",
                clock=lambda: NOW + timedelta(hours=24),
            )
    assert error.value.status_code == 410


def test_separate_recommendations_of_same_ad_each_credit_their_own_first_click(
    database: Database, opportunity: RecommendationResult
) -> None:
    assert opportunity.recommendation_id is not None
    with database.session() as session:
        second = recommend(session, opportunity.user_id, str(uuid4()), clock=lambda: NOW)
        assert second.recommendation_id is not None
        assert second.recommendation_id != opportunity.recommendation_id
        assert second.selection == opportunity.selection
        for recommendation_id in [opportunity.recommendation_id, second.recommendation_id]:
            record_event(session, recommendation_id, "impression", clock=lambda: NOW)
            record_event(session, recommendation_id, "click", clock=lambda: NOW)
    with database.transaction() as session:
        assert session.scalar(
            select(func.sum(Event.simulated_revenue)).where(
                Event.recommendation_id.in_(
                    [opportunity.recommendation_id, second.recommendation_id]
                )
            )
        ) == Decimal("2.5000")
