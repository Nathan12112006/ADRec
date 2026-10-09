from collections.abc import Iterator
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.cache.profiles import CachedUserProfile, RedisProfileCache
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.records import Recommendation, RequestOutcome, User
from app.seeding import SeedConfig, seed_database
from app.services.profiles import update_user_profile


def make_profile(database: Database) -> CachedUserProfile:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=1)
    seed_database(database, config, append=True)
    with database.session() as session:
        user = session.scalar(select(User).where(User.dataset_id == config.dataset_id))
        assert user is not None
        return CachedUserProfile(
            dataset_id=user.dataset_id,
            user_id=user.id,
            interests=tuple(user.interests),
            category_preferences=tuple(user.category_preferences),
            age_group=user.age_group,
            country=user.country,
            device=user.device,
        )


def test_redis_outage_falls_through_and_replay_stays_durable(
    database: Database, database_settings: Settings
) -> None:
    profile = make_profile(database)
    settings = Settings(
        database_url=database_settings.database_url,
        test_database_url=database_settings.test_database_url,
        redis_url=SecretStr("redis://127.0.0.1:1/0"),
        redis_connect_timeout_seconds=0.1,
        redis_socket_timeout_seconds=0.1,
    )
    app = create_app(settings)

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    key = f"cache-outage/{uuid4()}"
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/recommendations",
            json={"user_id": profile.user_id},
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 200, first.text
        replay = client.post(
            "/api/v1/recommendations",
            json={"user_id": profile.user_id},
            headers={"Idempotency-Key": key},
        )
        assert replay.status_code == 200
        assert first.json()["replayed"] is False and replay.json()["replayed"] is True
        assert {key: value for key, value in replay.json().items() if key != "replayed"} == {
            key: value for key, value in first.json().items() if key != "replayed"
        }
        metrics = app.state.profile_cache.metrics.snapshot()
        assert metrics["read_errors"] == 1
        assert metrics["bypasses"] == {"read_timeout": 1}
        health = client.get("/health/ready")
        assert health.status_code == 200
        details = health.json()
        assert details["status"] == "ready"
        assert details["dependencies"] == {"database": "ready", "redis": "degraded"}
        assert details["capabilities"] == {
            "retrieval": "exact_fallback",
            "retrieval_failure": None,
            "ranking_v1": True,
            "ranking_v2": False,
            "ctr_model_id": None,
        }
        assert details["profile_cache"]["read_errors"] == 1

    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(RequestOutcome)
                .where(RequestOutcome.request_key == key)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.user_id == profile.user_id)
            )
            == 1
        )


def test_profile_update_commits_before_best_effort_invalidation(database: Database) -> None:
    profile = make_profile(database)

    class ObservingRedis:
        invalidated = False

        def get(self, name: str) -> None:
            return None

        def set(self, name: str, value: str, *, ex: int) -> bool:
            return True

        def delete(self, *names: str) -> int:
            with database.session() as session:
                saved = session.get(User, profile.user_id)
                assert saved is not None
                assert saved.interests == ["updated-interest"]
            self.invalidated = True
            return 1

        def ping(self) -> bool:
            return True

        def close(self) -> None:
            return None

    client = ObservingRedis()
    cache = RedisProfileCache(client)
    updated = profile.model_copy(update={"interests": ("updated-interest",)})
    result = update_user_profile(database, cache, updated)
    assert result == updated
    assert client.invalidated


def test_profile_cache_keys_change_with_dataset_namespace() -> None:
    from app.cache.profiles import RedisProfileCache

    user_id = 42
    first = uuid4()
    second = uuid4()
    assert RedisProfileCache.key(first, user_id) != RedisProfileCache.key(second, user_id)
