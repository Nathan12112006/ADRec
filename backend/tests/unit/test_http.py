import json
import logging
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api import routes
from app.api.dependencies import get_session
from app.core.config import Settings
from app.core.errors import WorkflowError
from app.core.observability import JsonFormatter, logger
from app.main import create_app
from app.schemas.lifecycle import EventResponse, RecommendationResponse
from app.services.events import EventResult, EventType
from app.services.recommendations import AdSelection, RecommendationResult


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(
            database_url="postgresql+psycopg://demo:secret@127.0.0.1:1/adflow",
            test_database_url="postgresql+psycopg://demo:secret@127.0.0.1:1/adflow_test",
            db_connect_timeout_seconds=1,
        )
    )

    def session() -> Iterator[Session]:
        with Session() as value:
            yield value

    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value


@pytest.mark.parametrize(
    "body,key",
    [
        ({}, "valid"),
        ({"user_id": 0}, "valid"),
        ({"user_id": -1}, "valid"),
        ({"user_id": True}, "valid"),
        ({"user_id": "1"}, "valid"),
        ({"user_id": 1.0}, "valid"),
        ({"user_id": 2**63}, "valid"),
        ({"user_id": 1, "client_secret": "secret"}, "valid"),
        ({"user_id": 1}, None),
        ({"user_id": 1}, ""),
        ({"user_id": 1}, " "),
        ({"user_id": 1}, "a" * 256),
    ],
)
def test_recommendation_validation(
    client: TestClient, body: dict[str, object], key: str | None
) -> None:
    headers = {} if key is None else {"Idempotency-Key": key}
    response = client.post("/api/v1/recommendations", json=body, headers=headers)
    assert response.status_code == 422
    assert "secret" not in response.text
    assert response.json()["error"]["code"] in ("invalid_request", "invalid_request_key")
    assert response.headers["x-request-id"]


def test_duplicate_key_headers_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recommendations",
        json={"user_id": 1},
        headers=[("Idempotency-Key", "one"), ("Idempotency-Key", "two")],
    )
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["impression", "click"])
@pytest.mark.parametrize(
    "body", [{}, {"recommendation_id": "secret"}, {"recommendation_id": str(uuid4()), "user_id": 1}]
)
def test_event_validation(client: TestClient, endpoint: str, body: dict[str, object]) -> None:
    response = client.post(f"/api/v1/events/{endpoint}", json=body)
    assert response.status_code == 422
    assert "secret" not in response.text


def test_recommendation_schema_and_empty_no_ad(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection = AdSelection(
        id=7,
        advertiser_id=3,
        title="Ad",
        description="Description",
        target_url="https://example.com",
        category="sport",
        interests=("sport",),
        bid=Decimal("1.2500"),
        score=1,
    )
    result = RecommendationResult(1, datetime.now(timezone.utc), uuid4(), selection)

    def recommend(
        session: Session, user_id: int, request_key: str, *, clock: Callable[[], datetime]
    ) -> RecommendationResult:
        assert user_id == 1 and request_key == "key"
        return result

    monkeypatch.setattr(routes, "recommend", recommend)
    response = client.post(
        "/api/v1/recommendations", json={"user_id": 1}, headers={"Idempotency-Key": "key"}
    )
    assert response.status_code == 200
    parsed = RecommendationResponse.model_validate(response.json())
    assert parsed.recommendation_id == result.recommendation_id
    assert parsed.selection == selection
    assert response.json()["selection"]["predicted_ctr"] is None
    result = RecommendationResult(1, result.created_at, None, None)
    response = client.post(
        "/api/v1/recommendations", json={"user_id": 1}, headers={"Idempotency-Key": "key"}
    )
    assert response.status_code == 204 and response.content == b""
    assert "content-type" not in response.headers
    schema = client.get("/openapi.json").json()
    assert "204" in schema["paths"]["/api/v1/recommendations"]["post"]["responses"]


@pytest.mark.parametrize("event_type", ["impression", "click"])
def test_event_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, event_type: EventType
) -> None:
    identity = uuid4()
    result = EventResult(identity, event_type, 1, 7, datetime.now(timezone.utc), Decimal("1.25"))

    def record(
        session: Session,
        recommendation_id: object,
        kind: EventType,
        *,
        clock: Callable[[], datetime],
    ) -> EventResult:
        assert recommendation_id == identity and kind == event_type
        return result

    monkeypatch.setattr(routes, "record_event", record)
    response = client.post(
        f"/api/v1/events/{event_type}", json={"recommendation_id": str(identity)}
    )
    assert response.status_code == 200
    assert EventResponse.model_validate(response.json()).simulated_revenue == Decimal("1.25")


@pytest.mark.parametrize("status", [404, 409, 410, 422, 503])
def test_workflow_errors(client: TestClient, monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    def fail(
        session: Session, user_id: int, request_key: str, *, clock: Callable[[], datetime]
    ) -> RecommendationResult:
        raise WorkflowError(status, "safe_reason", "Safe message")

    monkeypatch.setattr(routes, "recommend", fail)
    response = client.post(
        "/api/v1/recommendations", json={"user_id": 1}, headers={"Idempotency-Key": "key"}
    )
    assert response.status_code == status
    assert response.json() == {"error": {"code": "safe_reason", "message": "Safe message"}}


def test_health_survives_database_loss(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "live"}
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert client.get("/health/live").status_code == 200


@pytest.mark.parametrize("database_failure", [True, False])
def test_safe_failures_and_request_logging(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, database_failure: bool
) -> None:
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(JsonFormatter().format(record))

    def fail(
        session: Session, user_id: int, request_key: str, *, clock: Callable[[], datetime]
    ) -> RecommendationResult:
        if database_failure:
            raise OperationalError("secret SQL", {}, Exception("password=secret"))
        raise RuntimeError("password=secret")

    monkeypatch.setattr(routes, "recommend", fail)
    handler = Capture()
    logger.addHandler(handler)
    try:
        response = client.post(
            "/api/v1/recommendations?secret=secret",
            json={"user_id": 1},
            headers={"Idempotency-Key": "secret"},
        )
    finally:
        logger.removeHandler(handler)
    assert response.status_code == (503 if database_failure else 500)
    assert "secret" not in response.text
    assert "secret" not in "".join(records)
    logged = json.loads(records[-1])
    assert logged["request_id"] == response.headers["x-request-id"]
    assert logged["user_id"] == 1
    assert logged["duration_ms"] >= 0
    assert logged["stages"]["recommendation_ms"] >= 0
    assert logged["route"] == "/api/v1/recommendations"
