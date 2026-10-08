import io
import json
import logging
from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.dependencies import get_database, get_session
from app.core.clock import utc_now
from app.core.config import Settings
from app.core.observability import JsonFormatter, logger
from app.db.session import Database
from app.main import create_app
from app.models.records import Event
from app.schemas.lifecycle import EventResponse, RecommendationResponse
from app.seeding import SeedConfig, generate_entities, seed_database
from app.services.events import record_event
from app.services.recommendations import recommend


@pytest.fixture
def client(database: Database, database_settings: Settings) -> Iterator[TestClient]:
    app = create_app(database_settings)

    def session() -> Iterator[Session]:
        with database.session() as value:
            yield value

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as value:
        yield value


def seeded_user(database: Database, *, ads: int = 1) -> int:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=ads)
    seed_database(database, config, append=True)
    return int(next(row["id"] for kind, row in generate_entities(config) if kind == "users"))


def test_http_lifecycle_replay_accounting_and_selection_logs(
    database: Database, client: TestClient
) -> None:
    user_id = seeded_user(database)
    key = str(uuid4())
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        response = client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 200
        recommendation = RecommendationResponse.model_validate(response.json())
        assert recommendation.selection.predicted_ctr is None
        replay = client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        )
        assert replay.json() == response.json()
        body = {"recommendation_id": str(recommendation.recommendation_id)}
        assert (
            client.post("/api/v1/events/click", json=body).json()["error"]["code"]
            == "impression_required"
        )
        for kind in ("impression", "click"):
            accepted = client.post(f"/api/v1/events/{kind}", json=body)
            assert accepted.status_code == 200
            event = EventResponse.model_validate(accepted.json())
            assert event.user_id == user_id and event.ad_id == recommendation.selection.id
            assert client.post(f"/api/v1/events/{kind}", json=body).json() == accepted.json()
        assert event.simulated_revenue == recommendation.selection.bid
        assert client.get("/health/ready").json() == {"status": "ready"}
    finally:
        logger.removeHandler(handler)
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.recommendation_id == recommendation.recommendation_id)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.sum(Event.simulated_revenue)).where(
                    Event.recommendation_id == recommendation.recommendation_id
                )
            )
            == recommendation.selection.bid
        )
    logs = [json.loads(line) for line in output.getvalue().splitlines()]
    selected = logs[0]
    assert selected["recommendation_id"] == str(recommendation.recommendation_id)
    assert selected["strategy"] == "interest-overlap" and selected["score"] >= 0
    assert selected["stages"]["selection_ms"] >= 0
    assert selected["stages"]["recommendation_ms"] >= selected["stages"]["selection_ms"]
    assert "selection_ms" not in logs[1]["stages"]  # Replay does not rerank.
    assert logs[-1]["stages"]["database_probe_ms"] >= 0
    assert "user_id" not in logs[-1] and "recommendation_id" not in logs[-1]
    assert key not in output.getvalue()


def test_http_no_ad_and_identity_errors(database: Database, client: TestClient) -> None:
    user_id = seeded_user(database, ads=0)
    key = str(uuid4())
    for _ in range(2):
        response = client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 204 and response.content == b""
    response = client.post(
        "/api/v1/recommendations",
        json={"user_id": seeded_user(database)},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 409
    response = client.post(
        "/api/v1/recommendations",
        json={"user_id": 9223372036854775807},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 404
    for kind in ("impression", "click"):
        response = client.post(f"/api/v1/events/{kind}", json={"recommendation_id": str(uuid4())})
        assert response.status_code == 404


def test_http_expiry_and_accepted_event_replay(database: Database, client: TestClient) -> None:
    user_id = seeded_user(database)
    key = str(uuid4())
    past = utc_now() - timedelta(days=2)
    with database.session() as session:
        saved = recommend(session, user_id, key, clock=lambda: past)
        assert saved.recommendation_id is not None
        record_event(session, saved.recommendation_id, "impression", clock=lambda: past)
    assert (
        client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        ).status_code
        == 410
    )
    body = {"recommendation_id": str(saved.recommendation_id)}
    assert client.post("/api/v1/events/impression", json=body).status_code == 200
    assert client.post("/api/v1/events/click", json=body).status_code == 410


def test_real_database_unavailability_returns_safe_failures(database_settings: Settings) -> None:
    url = make_url(database_settings.test_database_url.get_secret_value()).set(
        database=f"missing_{uuid4().hex}"
    )
    settings = Settings(
        database_url=url.render_as_string(hide_password=False),
        test_database_url=database_settings.test_database_url,
        db_connect_timeout_seconds=1,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": 1},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 503
        for kind in ("impression", "click"):
            response = client.post(
                f"/api/v1/events/{kind}", json={"recommendation_id": str(uuid4())}
            )
            assert response.status_code == 503
            assert url.database is not None and url.database not in response.text
            assert "Traceback" not in response.text
