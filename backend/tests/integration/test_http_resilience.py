"""Lifecycle guarantees through HTTP and the dedicated PostgreSQL database."""

import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.sql import Executable
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.dependencies import get_clock
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.records import Ad, Advertiser, Event, Recommendation, RequestOutcome, User
from app.seeding import SeedConfig, generate_entities, seed_database

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@dataclass
class ControlledClock:
    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now


@dataclass(frozen=True)
class Inventory:
    dataset_id: UUID
    user_id: int
    other_user_id: int
    ad_id: int
    advertiser_id: int


class LoseFirstResponse:
    """Fail at the transport boundary after the first successful selection commits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.lost = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def unreliable_send(message: Message) -> None:
            if (
                scope["type"] == "http"
                and scope["path"] == "/api/v1/recommendations"
                and message["type"] == "http.response.start"
                and message["status"] == 200
                and not self.lost
            ):
                self.lost = True
                raise ConnectionError("Simulated response loss after commit")
            await send(message)

        await self.app(scope, receive, unreliable_send)


@pytest.fixture
def inventory(database: Database) -> Inventory:
    config = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=1)
    seed_database(database, config, append=True)
    entities = list(generate_entities(config))
    users = [int(row["id"]) for kind, row in entities if kind == "users"]
    ad_id = next(int(row["id"]) for kind, row in entities if kind == "ads")
    advertiser_id = next(int(row["id"]) for kind, row in entities if kind == "advertisers")
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.id == ad_id).values(bid="1.2500"))
    return Inventory(config.dataset_id, users[0], users[1], ad_id, advertiser_id)


@pytest.fixture
def clock() -> ControlledClock:
    return ControlledClock()


@pytest.fixture
def client(
    database: Database,
    database_settings: Settings,
    clock: ControlledClock,
    request: pytest.FixtureRequest,
) -> Iterator[TestClient]:
    # Production session/lifespan dependencies run unchanged against TEST_DATABASE_URL.
    # The companion setting names an unused database; neither setting targets development.
    unused = make_url(database_settings.test_database_url.get_secret_value()).set(
        database=f"unused_http_{uuid4().hex}"
    )
    settings = Settings(
        **database_settings.model_dump(exclude={"database_url", "test_database_url"}),
        database_url=database_settings.test_database_url,
        test_database_url=unused.render_as_string(hide_password=False),
    )
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: clock
    transport_app = (
        LoseFirstResponse(app) if getattr(request, "param", None) == "lose_response" else app
    )
    with TestClient(transport_app) as value:
        yield value


@pytest.mark.parametrize("no_ad", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_request_key_expires_at_exactly_24_hours(
    database: Database,
    client: TestClient,
    inventory: Inventory,
    clock: ControlledClock,
    offset: int,
    no_ad: bool,
) -> None:
    if no_ad:
        with database.transaction() as session:
            session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    body = {"user_id": inventory.user_id}
    saved = client.post("/api/v1/recommendations", json=body, headers={"Idempotency-Key": key})
    assert saved.status_code == (204 if no_ad else 200)
    with database.transaction() as session:
        outcome = session.get(RequestOutcome, key)
        assert outcome is not None and outcome.created_at == NOW
        original_id = outcome.recommendation_id
        # A no-ad key remains a no-ad key even after eligible inventory appears.
        session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=True))
    clock.now = NOW + timedelta(hours=24, microseconds=offset)
    replay = client.post("/api/v1/recommendations", json=body, headers={"Idempotency-Key": key})
    if offset < 0:
        assert replay.status_code == saved.status_code
        if saved.status_code == 200:
            assert saved.json()["replayed"] is False
            assert replay.json()["replayed"] is True
            assert {k: v for k, v in replay.json().items() if k != "replayed"} == {
                k: v for k, v in saved.json().items() if k != "replayed"
            }
        else:
            assert replay.content == saved.content
    else:
        assert replay.status_code == 410
        assert replay.json()["error"]["code"] == "request_key_expired"
    conflict = client.post(
        "/api/v1/recommendations",
        json={"user_id": inventory.other_user_id},
        headers={"Idempotency-Key": key},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "request_key_user_conflict"
    with database.session() as session:
        outcome = session.get(RequestOutcome, key)
        assert outcome is not None and outcome.recommendation_id == original_id
        assert session.scalar(
            select(func.count())
            .select_from(Recommendation)
            .where(Recommendation.user_id == inventory.user_id)
        ) == (0 if no_ad else 1)


@pytest.mark.parametrize("event_type", ["impression", "click"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_first_event_expires_at_creation_plus_24_hours(
    client: TestClient, inventory: Inventory, clock: ControlledClock, event_type: str, offset: int
) -> None:
    selected = client.post(
        "/api/v1/recommendations",
        json={"user_id": inventory.user_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert selected.status_code == 200
    body = {"recommendation_id": selected.json()["recommendation_id"]}
    if event_type == "click":
        assert client.post("/api/v1/events/impression", json=body).status_code == 200
    clock.now = NOW + timedelta(hours=24, microseconds=offset)
    accepted = client.post(f"/api/v1/events/{event_type}", json=body)
    if offset < 0:
        assert accepted.status_code == 200
        assert (
            datetime.fromisoformat(accepted.json()["created_at"].replace("Z", "+00:00"))
            == clock.now
        )
    else:
        assert accepted.status_code == 410
        assert accepted.json()["error"]["code"] == "recommendation_expired"


@pytest.mark.parametrize("client", ["lose_response"], indirect=True)
def test_lost_response_replays_original_selection_after_inventory_changes(
    database: Database, client: TestClient, inventory: Inventory
) -> None:
    key = str(uuid4())
    body = {"user_id": inventory.user_id}
    with pytest.raises(ConnectionError, match="response loss after commit"):
        client.post("/api/v1/recommendations", json=body, headers={"Idempotency-Key": key})
    with database.transaction() as session:
        outcome = session.get(RequestOutcome, key)
        assert outcome is not None and outcome.recommendation_id is not None
        original_id = outcome.recommendation_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.recommendation_id == original_id)
            )
            == 0
        )
        session.execute(
            update(Ad)
            .where(Ad.id == inventory.ad_id)
            .values(bid=9, active=False, title="Changed title")
        )
        session.execute(
            update(Advertiser).where(Advertiser.id == inventory.advertiser_id).values(active=False)
        )
        session.execute(update(User).where(User.id == inventory.user_id).values(interests=[]))
    replay = client.post("/api/v1/recommendations", json=body, headers={"Idempotency-Key": key})
    assert replay.status_code == 200
    assert replay.json()["recommendation_id"] == str(original_id)
    assert Decimal(replay.json()["selection"]["bid"]) == Decimal("1.25")
    assert replay.json()["selection"]["title"] != "Changed title"
    event_body = {"recommendation_id": str(original_id)}
    rejected = client.post("/api/v1/events/click", json=event_body)
    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "impression_required"
    assert client.post("/api/v1/events/impression", json=event_body).status_code == 200
    accepted = client.post("/api/v1/events/click", json=event_body)
    assert accepted.status_code == 200
    assert Decimal(accepted.json()["simulated_revenue"]) == Decimal("1.25")
    assert accepted.json()["ad_id"] == inventory.ad_id
    assert (
        client.post(
            "/api/v1/recommendations", json=body, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 204
    )
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.user_id == inventory.user_id)
            )
            == 1
        )
        assert session.scalar(
            select(func.sum(Event.simulated_revenue)).where(Event.recommendation_id == original_id)
        ) == Decimal("1.25")


@pytest.mark.parametrize("bid", [Decimal("0"), Decimal("1.25")])
def test_accepted_events_replay_after_expiry_without_additional_credit(
    database: Database,
    client: TestClient,
    inventory: Inventory,
    clock: ControlledClock,
    bid: Decimal,
) -> None:
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(bid=bid))
    selected = client.post(
        "/api/v1/recommendations",
        json={"user_id": inventory.user_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert selected.status_code == 200
    body = {"recommendation_id": selected.json()["recommendation_id"]}
    saved = [client.post(f"/api/v1/events/{kind}", json=body) for kind in ("impression", "click")]
    assert [response.status_code for response in saved] == [200, 200]
    for moment in (NOW + timedelta(hours=24), NOW + timedelta(days=2)):
        clock.now = moment
        for kind, original in zip(("impression", "click"), saved, strict=True):
            replay = client.post(f"/api/v1/events/{kind}", json=body)
            assert replay.status_code == 200 and replay.json() == original.json()
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.recommendation_id == UUID(body["recommendation_id"]))
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.sum(Event.simulated_revenue)).where(
                    Event.recommendation_id == UUID(body["recommendation_id"])
                )
            )
            == bid
        )


def race_posts(
    database: Database, gate: Executable, operation: Callable[[int], Response]
) -> list[Response]:
    """Observe four transactions waiting in PostgreSQL before releasing their gate."""
    with ThreadPoolExecutor(max_workers=4) as workers:
        with database.session() as blocker:
            blocker.execute(gate)
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            pending: list[Future[Response]] = [
                workers.submit(operation, index) for index in range(4)
            ]
            try:
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    assert not any(result.done() for result in pending)
                    with database.session() as observer:
                        blocked = observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname = current_database() "
                                "AND :blocker = ANY(pg_blocking_pids(pid))"
                            ),
                            {"blocker": blocker_pid},
                        )
                    if blocked == 4:
                        break
                    time.sleep(0.01)
                else:
                    pytest.fail("Four HTTP transactions did not overlap at the PostgreSQL gate")
            finally:
                blocker.rollback()
        return [result.result(timeout=8) for result in pending]


@pytest.mark.parametrize("no_ad", [False, True])
def test_racing_request_keys_create_one_outcome(
    database: Database, client: TestClient, inventory: Inventory, no_ad: bool
) -> None:
    if no_ad:
        with database.transaction() as session:
            session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
    key = str(uuid4())
    responses = race_posts(
        database,
        select(User).where(User.id == inventory.user_id).with_for_update(),
        lambda _: client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        ),
    )
    assert [response.status_code for response in responses] == [204 if no_ad else 200] * 4
    if no_ad:
        assert all(response.content == b"" for response in responses)
    else:
        payloads = [response.json() for response in responses]
        assert sorted(payload["replayed"] for payload in payloads) == [False, True, True, True]
        stable_payloads = [
            {key: value for key, value in payload.items() if key != "replayed"}
            for payload in payloads
        ]
        assert all(payload == stable_payloads[0] for payload in stable_payloads)
    with database.session() as session:
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


def test_racing_different_users_cannot_share_a_request_key(
    database: Database, client: TestClient, inventory: Inventory
) -> None:
    key = str(uuid4())
    users = (inventory.user_id, inventory.other_user_id)
    responses = race_posts(
        database,
        select(User).where(User.id.in_(users)).with_for_update(),
        lambda index: client.post(
            "/api/v1/recommendations",
            json={"user_id": users[index % 2]},
            headers={"Idempotency-Key": key},
        ),
    )
    assert sorted(response.status_code for response in responses) == [200, 200, 409, 409]
    winners = [response.json() for response in responses if response.status_code == 200]
    assert sorted(winner["replayed"] for winner in winners) == [False, True]
    assert {key: value for key, value in winners[0].items() if key != "replayed"} == {
        key: value for key, value in winners[1].items() if key != "replayed"
    }
    with database.session() as session:
        outcome = session.get(RequestOutcome, key)
        assert outcome is not None and outcome.user_id == winners[0]["user_id"]
        assert (
            session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.user_id.in_(users))
            )
            == 1
        )


@pytest.mark.parametrize("event_type", ["impression", "click"])
def test_racing_duplicate_events_credit_once(
    database: Database, client: TestClient, inventory: Inventory, event_type: str
) -> None:
    selected = client.post(
        "/api/v1/recommendations",
        json={"user_id": inventory.user_id},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert selected.status_code == 200
    body = {"recommendation_id": selected.json()["recommendation_id"]}
    if event_type == "click":
        assert client.post("/api/v1/events/impression", json=body).status_code == 200
    responses = race_posts(
        database,
        text("LOCK TABLE events IN SHARE MODE"),
        lambda _: client.post(f"/api/v1/events/{event_type}", json=body),
    )
    assert [response.status_code for response in responses] == [200] * 4
    assert all(response.json() == responses[0].json() for response in responses)
    with database.session() as session:
        count, revenue = session.execute(
            select(func.count(), func.sum(Event.simulated_revenue)).where(
                Event.recommendation_id == UUID(body["recommendation_id"]),
                Event.event_type == event_type,
            )
        ).one()
    assert count == 1
    assert revenue == (Decimal("1.25") if event_type == "click" else Decimal("0"))


@contextmanager
def reject_write(
    database: Database,
    table: Literal["request_outcomes", "events"],
    predicate: str,
    *,
    deferred: bool,
) -> Iterator[None]:
    """Inject a real insert/commit failure, scoped to one synthetic opportunity."""
    name = f"fail_ticket08_{uuid4().hex}"
    with database.transaction() as session:
        session.execute(
            text(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'Injected private storage failure'; END; $$"
            )
        )
        session.execute(
            text(
                f"CREATE CONSTRAINT TRIGGER {name} AFTER INSERT ON {table} "
                + ("DEFERRABLE INITIALLY DEFERRED " if deferred else "NOT DEFERRABLE ")
                + f"FOR EACH ROW WHEN ({predicate}) EXECUTE FUNCTION {name}()"
            )
        )
    try:
        yield
    finally:
        with database.transaction() as session:
            session.execute(text(f"DROP TRIGGER {name} ON {table}"))
            session.execute(text(f"DROP FUNCTION {name}()"))


@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("operation", ["recommendation", "no_ad", "impression", "click"])
def test_failed_insert_or_commit_returns_503_without_acceptance_then_retry_succeeds(
    database: Database, client: TestClient, inventory: Inventory, operation: str, deferred: bool
) -> None:
    key = str(uuid4())
    if operation in ("recommendation", "no_ad"):
        if operation == "no_ad":
            with database.transaction() as session:
                session.execute(update(Ad).where(Ad.id == inventory.ad_id).values(active=False))
        with reject_write(
            database, "request_outcomes", f"NEW.request_key = '{key}'", deferred=deferred
        ):
            response = client.post(
                "/api/v1/recommendations",
                json={"user_id": inventory.user_id},
                headers={"Idempotency-Key": key},
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "recommendation_unavailable"
            assert "Injected" not in response.text and "private" not in response.text
            with database.session() as session:
                assert session.get(RequestOutcome, key) is None
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(Recommendation)
                        .where(Recommendation.user_id == inventory.user_id)
                    )
                    == 0
                )
        retry = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert retry.status_code == (204 if operation == "no_ad" else 200)
        replay = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert replay.status_code == retry.status_code
        if retry.status_code == 200:
            assert retry.json()["replayed"] is False
            assert replay.json()["replayed"] is True
            assert {
                field: value for field, value in replay.json().items() if field != "replayed"
            } == {field: value for field, value in retry.json().items() if field != "replayed"}
        else:
            assert replay.content == retry.content
    else:
        selected = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert selected.status_code == 200
        recommendation_id = UUID(selected.json()["recommendation_id"])
        body = {"recommendation_id": str(recommendation_id)}
        if operation == "click":
            assert client.post("/api/v1/events/impression", json=body).status_code == 200
        predicate = (
            f"NEW.recommendation_id = '{recommendation_id}'::uuid "
            f"AND NEW.event_type = '{operation}'"
        )
        with reject_write(database, "events", predicate, deferred=deferred):
            response = client.post(f"/api/v1/events/{operation}", json=body)
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "event_unavailable"
            assert "Injected" not in response.text and "private" not in response.text
            with database.session() as session:
                assert session.get(Event, (recommendation_id, operation)) is None
                assert session.scalar(
                    select(func.coalesce(func.sum(Event.simulated_revenue), 0)).where(
                        Event.recommendation_id == recommendation_id
                    )
                ) == Decimal("0")
        retry = client.post(f"/api/v1/events/{operation}", json=body)
        assert retry.status_code == 200
        replay = client.post(f"/api/v1/events/{operation}", json=body)
        assert replay.status_code == 200 and replay.json() == retry.json()
        with database.session() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Event)
                    .where(
                        Event.recommendation_id == recommendation_id, Event.event_type == operation
                    )
                )
                == 1
            )
            assert session.scalar(
                select(func.sum(Event.simulated_revenue)).where(
                    Event.recommendation_id == recommendation_id
                )
            ) == (Decimal("1.25") if operation == "click" else Decimal("0"))
