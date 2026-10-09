from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.core.config import Settings
from app.core.observability import stages
from app.db.catalog import read_catalog
from app.db.session import Database
from app.main import create_app
from app.models.records import Ad, Recommendation, User
from app.retrieval.snapshots import HnswSettings, build_snapshot
from app.seeding import SeedConfig, seed_database
from app.services.recommendations import recommend


def test_ranking_only_sees_the_configured_candidate_set(database: Database) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=3)
    seed_database(database, config, append=True)
    with database.transaction() as session:
        user = session.scalar(select(User).where(User.dataset_id == config.dataset_id))
        assert user is not None
        user.interests = ["sports"]
        user_id = user.id
        ads = list(
            session.scalars(select(Ad).where(Ad.dataset_id == config.dataset_id).order_by(Ad.id))
        )
        for ad in ads:
            ad.active = True
            ad.category = "sports"
            ad.interests = ["sports"]
            ad.bid = Decimal("1")
        # The baseline would prefer this high bid, but its cosine is lower.
        ads[2].interests = ["sports", "music"]
        ads[2].bid = Decimal("99")
        expected_id = ads[0].id
    with database.session() as session:
        result = recommend(session, user_id, str(uuid4()), candidate_limit=1)
    assert result.selection is not None
    assert result.selection.id == expected_id
    assert result.selection.retrieval is not None
    assert result.selection.retrieval.returned_count == 1
    assert result.selection.retrieval.mode == "exact_fallback"


@pytest.mark.parametrize("hnsw", [None, HnswSettings(m=16, ef_construction=80, ef_search=64)])
def test_http_uses_configured_index_and_limit_and_replays_saved_context(
    database: Database, database_settings: Settings, tmp_path: Path, hnsw: HnswSettings | None
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=5)
    seed_database(database, config, append=True)
    with database.session() as session:
        user_id = session.scalar(select(User.id).where(User.dataset_id == config.dataset_id))
        catalog = read_catalog(session, config.dataset_id)
    build_snapshot(
        tmp_path / "index",
        catalog.entries,
        dataset_id=config.dataset_id,
        catalog_version=catalog.version,
        hnsw=hnsw,
    )
    app = create_app(
        database_settings.model_copy(
            update={"retrieval_candidate_limit": 2, "retrieval_index_path": tmp_path / "index"}
        )
    )

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        key = str(uuid4())
        response = client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 200
        context = response.json()["selection"]["retrieval"]
        assert context["mode"] == ("exact" if hnsw is None else "hnsw")
        assert context["returned_count"] == context["requested_count"] == 2
        # A replacement index must not change this opportunity's saved decision.
        with pytest.raises(ValueError):
            app.state.snapshots.reload(tmp_path / "missing")
        replay = client.post(
            "/api/v1/recommendations", json={"user_id": user_id}, headers={"Idempotency-Key": key}
        )
        assert response.json()["replayed"] is False and replay.json()["replayed"] is True
        assert {field: value for field, value in replay.json().items() if field != "replayed"} == {
            field: value for field, value in response.json().items() if field != "replayed"
        }
    with database.session() as session:
        saved = session.get(Recommendation, response.json()["recommendation_id"])
        assert saved is not None
        assert saved.selected_ad["retrieval"] == context


@pytest.mark.parametrize("failure", ["missing_index", "corrupt_index", "stale_index"])
def test_http_falls_back_to_current_inventory_for_unusable_snapshots(
    database: Database, database_settings: Settings, tmp_path: Path, failure: str
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=3)
    seed_database(database, config, append=True)
    path = tmp_path / "index"
    with database.session() as session:
        user_id = session.scalar(select(User.id).where(User.dataset_id == config.dataset_id))
        catalog = read_catalog(session, config.dataset_id)
    if failure != "missing_index":
        build_snapshot(
            path, catalog.entries, dataset_id=config.dataset_id, catalog_version=catalog.version
        )
        if failure == "corrupt_index":
            (path / "manifest.json").write_text("broken")
        else:
            with database.transaction() as session:
                ad = session.get(Ad, catalog.entries[0].ad_id)
                assert ad is not None
                ad.active = False
    app = create_app(database_settings.model_copy(update={"retrieval_index_path": path}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": user_id},
            headers={"Idempotency-Key": str(uuid4())},
        )
    assert response.status_code == 200
    context = response.json()["selection"]["retrieval"]
    assert context["mode"] == "exact_fallback"
    assert context["fallback_reason"] == failure
    assert context["returned_count"] == (2 if failure == "stale_index" else 3)


def test_empty_interests_and_no_ad_replay_do_not_require_an_index(database: Database) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=2)
    seed_database(database, config, append=True)
    with database.transaction() as session:
        user = session.scalar(select(User).where(User.dataset_id == config.dataset_id))
        assert user is not None
        user.interests = []
        user_id = user.id
        ads = list(session.scalars(select(Ad).where(Ad.dataset_id == config.dataset_id)))
        ads[0].bid = Decimal("99")
        expected = ads[0].id
    with database.session() as session:
        result = recommend(session, user_id, str(uuid4()), candidate_limit=1)
    assert result.selection is not None and result.selection.id == expected
    assert result.selection.score == 0
    assert result.selection.retrieval is not None
    assert result.selection.retrieval.mode == "nonpersonalized"
    with database.transaction() as session:
        for ad in session.scalars(select(Ad).where(Ad.dataset_id == config.dataset_id)):
            ad.active = False
    key = str(uuid4())
    with database.session() as session:
        saved = recommend(session, user_id, key)
    assert saved.selection is None
    with database.transaction() as session:
        restored = session.get(Ad, expected)
        assert restored is not None
        restored.active = True
    timings: dict[str, float] = {}
    token = stages.set(timings)
    try:
        with database.session() as session:
            assert recommend(session, user_id, key) == saved
        assert "retrieval_ms" not in timings
    finally:
        stages.reset(token)


def test_request_timings_separate_retrieval_ranking_and_database_and_replay_skips_retrieval(
    database: Database,
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=3)
    seed_database(database, config, append=True)
    with database.session() as session:
        user_id = session.scalar(select(User.id).where(User.dataset_id == config.dataset_id))
    assert user_id is not None
    key = str(uuid4())
    timings: dict[str, float] = {}
    token = stages.set(timings)
    try:
        with database.session() as session:
            saved = recommend(session, user_id, key)
        assert set(timings) >= {
            "vector_ms",
            "metadata_ms",
            "fallback_ms",
            "ranking_ms",
            "database_ms",
        }
        assert all(value >= 0 for value in timings.values())
        timings.clear()
        with database.session() as session:
            assert recommend(session, user_id, key) == saved
        assert "retrieval_ms" not in timings and "ranking_ms" not in timings
        assert "database_ms" in timings
    finally:
        stages.reset(token)
