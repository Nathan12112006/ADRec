from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.dependencies import get_database, get_session
from app.core.clock import utc_now
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.records import Ad
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


def test_overview_reconciles_current_dataset_and_live_events(
    database: Database, client: TestClient
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=2)
    seed_database(database, config, append=True)
    user_ids = [row["id"] for kind, row in generate_entities(config) if kind == "users"]
    now = utc_now()
    with database.session() as session:
        selected = recommend(session, user_ids[0], str(uuid4()), clock=lambda: now)
    assert selected.recommendation_id is not None and selected.selection is not None
    with database.session() as session:
        record_event(
            session,
            selected.recommendation_id,
            "impression",
            clock=lambda: now,
        )
        record_event(
            session,
            selected.recommendation_id,
            "click",
            clock=lambda: now,
        )
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.dataset_id == config.dataset_id).values(active=False))
    with database.session() as session:
        no_ad = recommend(session, user_ids[1], str(uuid4()), clock=lambda: now)
    assert no_ad.recommendation_id is None

    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200, response.text
    overview = response.json()
    assert overview["availability"] == "available"
    assert overview["dataset_id"] == str(config.dataset_id)
    assert overview["window_scope"] == "dataset_lifetime"
    assert overview["window_start"] == overview["dataset_created_at"]
    assert overview["window_end"] == overview["as_of"]
    assert overview["coverage"] == "durable_postgresql_snapshot"
    assert overview["provisional"] is True
    assert overview["users"] == 2
    assert overview["advertisers"] == 1
    assert overview["active_advertisers"] == 1
    assert overview["ads"] == 2
    assert overview["active_ads"] == 0
    assert overview["recommendations"] == 1
    assert overview["request_outcomes"] == 2
    assert overview["no_ad_outcomes"] == 1
    assert overview["exposed_users"] == 1
    assert overview["impressions"] == 1
    assert overview["clicks"] == 1
    assert Decimal(overview["observed_ctr"]) == Decimal(1)
    assert Decimal(overview["simulated_revenue"]) == selected.selection.bid


def test_metrics_exposes_window_cache_scope_and_unavailable_telemetry(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200, response.text
    metrics = response.json()
    assert metrics["window_end"] == metrics["as_of"]
    assert metrics["retention_seconds"] == 900
    assert metrics["coverage_complete"] is False
    assert metrics["coverage_scope"] == "process_local_rolling_window"
    assert metrics["sample_count"] == 0
    assert metrics["populations"] == []
    assert metrics["cache"]["scope"] == "process_lifetime"
    assert metrics["cache"]["hit_ratio"] is None
    assert metrics["cache_health"] == "disabled"
    assert metrics["capabilities"]["retrieval"] == "exact_fallback"
    assert metrics["capabilities"]["ranking_v1"] is True
    assert metrics["capabilities"]["ranking_v2"] is False
    assert metrics["database_readiness_path"] == "/health/ready"
