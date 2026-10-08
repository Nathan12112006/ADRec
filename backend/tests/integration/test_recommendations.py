import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import partial
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update

from app.core.config import Settings
from app.core.errors import WorkflowError
from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset, Recommendation, RequestOutcome, User
from app.services.recommendations import RecommendationResult, recommend

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Inventory:
    dataset_id: UUID
    user_id: int
    other_user_id: int
    advertiser_id: int
    ad_id: int


@pytest.fixture
def inventory(database: Database) -> Inventory:
    with database.transaction() as session:
        dataset = Dataset(seed=5, generator_version="recommendation-test", configuration={})
        session.add(dataset)
        session.flush()
        users = [
            User(
                dataset_id=dataset.id,
                interests=["sports"],
                category_preferences=[],
                age_group="25-34",
                country="US",
                device="mobile",
            )
            for _ in range(2)
        ]
        advertiser = Advertiser(dataset_id=dataset.id, name="Synthetic advertiser", active=True)
        session.add_all([*users, advertiser])
        session.flush()
        ad = Ad(
            dataset_id=dataset.id,
            advertiser_id=advertiser.id,
            title="Original title",
            description="Synthetic ad",
            target_url="https://example.invalid/ad",
            category="sports",
            interests=["sports", "sports"],
            bid=Decimal("1.2500"),
            active=True,
        )
        session.add(ad)
        session.flush()
        return Inventory(dataset.id, users[0].id, users[1].id, advertiser.id, ad.id)


def test_new_opportunity_commits_a_complete_baseline_selection(
    database: Database, inventory: Inventory
) -> None:
    with database.session() as session:
        result = recommend(session, inventory.user_id, str(uuid4()), clock=lambda: NOW)
        assert not session.in_transaction()
    assert result.recommendation_id is not None
    assert result.created_at == NOW
    assert result.user_id == inventory.user_id
    assert result.selection is not None
    assert result.selection.id == inventory.ad_id
    assert result.selection.title == "Original title"
    assert result.selection.bid == Decimal("1.2500")
    assert result.selection.score == 1


def test_response_loss_retry_replays_snapshot_after_inventory_and_profile_changes(
    database: Database, inventory: Inventory
) -> None:
    key = str(uuid4())
    with database.session() as session:
        saved = recommend(session, inventory.user_id, key, clock=lambda: NOW)
    # A client that lost this response retries after mutable inventory/profile changes.
    with database.transaction() as session:
        session.execute(
            update(Ad).where(Ad.id == inventory.ad_id).values(bid=9, title="Changed", active=False)
        )
        session.execute(update(User).where(User.id == inventory.user_id).values(interests=[]))
    with database.session() as session:
        assert recommend(session, inventory.user_id, key, clock=lambda: NOW) == saved


def test_no_ad_outcome_replays_even_after_inventory_becomes_eligible(
    database: Database, inventory: Inventory
) -> None:
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    with database.session() as session:
        saved = recommend(session, inventory.user_id, key, clock=lambda: NOW)
    assert saved.recommendation_id is None and saved.selection is None
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=True))
    with database.session() as session:
        assert recommend(session, inventory.user_id, key, clock=lambda: NOW) == saved
        fresh = recommend(session, inventory.user_id, str(uuid4()), clock=lambda: NOW)
    assert fresh.selection is not None


@pytest.mark.parametrize("no_ad", [False, True])
def test_key_user_conflict_precedes_expiration(
    database: Database, inventory: Inventory, no_ad: bool
) -> None:
    if no_ad:
        with database.transaction() as session:
            session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    with database.session() as session:
        recommend(session, inventory.user_id, key, clock=lambda: NOW)
        with pytest.raises(WorkflowError) as error:
            recommend(session, inventory.other_user_id, key, clock=lambda: NOW + timedelta(days=2))
    assert error.value.status_code == 409
    assert error.value.code == "request_key_user_conflict"


@pytest.mark.parametrize("no_ad", [False, True])
def test_replay_expires_at_exactly_24_hours_without_recycling_key(
    database: Database, inventory: Inventory, no_ad: bool
) -> None:
    if no_ad:
        with database.transaction() as session:
            session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    with database.session() as session:
        saved = recommend(session, inventory.user_id, key, clock=lambda: NOW)
        assert (
            recommend(
                session,
                inventory.user_id,
                key,
                clock=lambda: NOW + timedelta(hours=24, microseconds=-1),
            )
            == saved
        )
        for offset in [timedelta(hours=24), timedelta(days=2)]:
            with pytest.raises(WorkflowError) as error:
                recommend(session, inventory.user_id, key, clock=partial(NOW.__add__, offset))
            assert error.value.status_code == 410
            assert error.value.code == "request_key_expired"


def test_unknown_user_returns_404(database: Database) -> None:
    with database.session() as session:
        with pytest.raises(WorkflowError) as error:
            recommend(session, 2**63 - 1, str(uuid4()))
        assert not session.in_transaction()
    assert error.value.status_code == 404


@pytest.mark.parametrize("no_ad", [False, True])
def test_racing_retries_create_one_durable_outcome(
    database: Database, inventory: Inventory, no_ad: bool
) -> None:
    if no_ad:
        with database.transaction() as session:
            session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    start = Barrier(8)

    def request() -> object:
        start.wait(timeout=10)
        with database.session() as session:
            return recommend(session, inventory.user_id, key, clock=lambda: NOW)

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: request(), range(8)))
    assert all(result == results[0] for result in results)
    with database.transaction() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(RequestOutcome)
                .where(RequestOutcome.request_key == key)
            )
            == 1
        )
        assert session.scalar(
            select(func.count())
            .select_from(Recommendation)
            .where(Recommendation.user_id == inventory.user_id)
        ) == (0 if no_ad else 1)


def test_database_unavailable_returns_safe_503(database_settings: Settings) -> None:
    settings = Settings(
        database_url=database_settings.database_url,
        test_database_url=(
            f"postgresql+psycopg://adflow@127.0.0.1:15432/missing_ticket05_{uuid4().hex}"
        ),
        db_connect_timeout_seconds=1,
    )
    unavailable = Database(settings, use_test_database=True)
    try:
        with unavailable.session() as session:
            with pytest.raises(WorkflowError) as error:
                recommend(session, 1, str(uuid4()))
            assert not session.in_transaction()
        assert error.value.status_code == 503
        assert "postgresql" not in str(error.value).lower()
        assert "missing_ticket05" not in str(error.value)
    finally:
        unavailable.dispose()


@pytest.mark.parametrize("deferred", [False, True])
def test_durable_write_failure_rolls_back_selection_and_key_then_retry_succeeds(
    database: Database, inventory: Inventory, deferred: bool
) -> None:
    name = f"fail_ticket05_{uuid4().hex}"
    with database.transaction() as session:
        session.execute(
            text(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'Injected commit failure'; END; $$"
            )
        )
        session.execute(
            text(
                f"CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON request_outcomes "
                + ("DEFERRABLE INITIALLY DEFERRED " if deferred else "NOT DEFERRABLE ")
                + "FOR EACH ROW "
                f"WHEN (NEW.user_id = {inventory.user_id}) EXECUTE FUNCTION {name}()"
            )
        )
    key = str(uuid4())
    try:
        with database.session() as session:
            with pytest.raises(WorkflowError) as error:
                recommend(session, inventory.user_id, key, clock=lambda: NOW)
            assert not session.in_transaction()
        assert error.value.status_code == 503
        assert "Injected" not in str(error.value)
        with database.transaction() as session:
            assert session.get(RequestOutcome, key) is None
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Recommendation)
                    .where(Recommendation.user_id == inventory.user_id)
                )
                == 0
            )
    finally:
        with database.transaction() as session:
            session.execute(text(f"DROP TRIGGER {name} ON request_outcomes"))
            session.execute(text(f"DROP FUNCTION {name}()"))
    with database.session() as session:
        assert recommend(session, inventory.user_id, key, clock=lambda: NOW).selection is not None


@pytest.mark.parametrize("change", ["bid", "interests", "ad_active", "advertiser_active"])
def test_inventory_edit_during_selection_is_revalidated_before_persistence(
    database: Database, inventory: Inventory, change: str
) -> None:
    with database.transaction() as session:
        alternate = Ad(
            dataset_id=inventory.dataset_id,
            advertiser_id=inventory.advertiser_id,
            title="Alternate",
            description="Synthetic alternative",
            target_url="https://example.invalid/alternate",
            category="sports",
            interests=["sports"],
            bid=Decimal("1"),
            active=True,
        )
        session.add(alternate)
        session.flush()
        alternate_id = alternate.id

    def request() -> RecommendationResult:
        with database.session() as session:
            return recommend(session, inventory.user_id, str(uuid4()), clock=lambda: NOW)

    # An uncommitted edit leaves the old winner visible to the initial MVCC scan.
    with ThreadPoolExecutor(max_workers=1) as workers:
        with database.session() as editor:
            editor_pid = editor.scalar(text("SELECT pg_backend_pid()"))
            if change == "advertiser_active":
                editor.execute(
                    update(Advertiser)
                    .where(Advertiser.id == inventory.advertiser_id)
                    .values(active=False)
                )
            else:
                values = (
                    {"bid": Decimal("0")}
                    if change == "bid"
                    else {"interests": ["music"]}
                    if change == "interests"
                    else {"active": False}
                )
                editor.execute(update(Ad).where(Ad.id == inventory.ad_id).values(**values))
            pending = workers.submit(request)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                assert not pending.done(), (
                    "Service returned without waiting to revalidate inventory"
                )
                with database.session() as observer:
                    blocked = observer.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE :editor = ANY(pg_blocking_pids(pid)))"
                        ),
                        {"editor": editor_pid},
                    )
                if blocked:
                    break
                time.sleep(0.01)
            else:
                pytest.fail("Service did not reach inventory revalidation lock")
            editor.commit()
        result = pending.result(timeout=8)
    if change == "advertiser_active":
        assert result.selection is None
    else:
        assert result.selection is not None
        assert result.selection.id == alternate_id
        assert result.selection.bid == Decimal("1")
        assert result.selection.score == 1


@pytest.mark.parametrize("key", ["", "   ", "x" * 256])
def test_request_key_is_required_and_bounded(
    database: Database, inventory: Inventory, key: str
) -> None:
    with database.session() as session:
        with pytest.raises(WorkflowError) as error:
            recommend(session, inventory.user_id, key)
        assert not session.in_transaction()
    assert error.value.status_code == 422


def test_concurrent_different_users_cannot_share_a_request_key(
    database: Database, inventory: Inventory
) -> None:
    key = str(uuid4())
    start = Barrier(2)

    def request(user_id: int) -> RecommendationResult | WorkflowError:
        start.wait(timeout=10)
        with database.session() as session:
            try:
                return recommend(session, user_id, key, clock=lambda: NOW)
            except WorkflowError as error:
                return error

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(request, [inventory.user_id, inventory.other_user_id]))
    successful = [result for result in results if isinstance(result, RecommendationResult)]
    conflicts = [result for result in results if isinstance(result, WorkflowError)]
    assert len(successful) == len(conflicts) == 1
    assert conflicts[0].status_code == 409
    with database.session() as session:
        assert recommend(session, successful[0].user_id, key, clock=lambda: NOW) == successful[0]
