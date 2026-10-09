from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from redis import Redis
from redis.connection import Connection, ConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError

from app.cache.profiles import CachedUserProfile, RedisProfileCache, create_profile_cache
from app.core.config import Settings


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiry_at: dict[str, int] = {}
        self.now = 100
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, str, int]] = []
        self.delete_calls: list[str] = []
        self.fail_get = False
        self.fail_set = False
        self.fail_delete = False
        self.fail_ping = False

    def get(self, name: str) -> str | None:
        self.get_calls.append(name)
        if self.fail_get:
            raise RedisConnectionError("redis unavailable")
        if name in self.expiry_at and self.expiry_at[name] <= self.now:
            self.values.pop(name, None)
            self.expiry_at.pop(name, None)
        return self.values.get(name)

    def set(self, name: str, value: str, *, ex: int) -> bool:
        self.set_calls.append((name, value, ex))
        if self.fail_set:
            raise RedisConnectionError("redis unavailable")
        self.values[name] = value
        self.expiry_at[name] = self.now + ex
        return True

    def delete(self, *names: str) -> int:
        self.delete_calls.extend(names)
        if self.fail_delete:
            raise RedisConnectionError("redis unavailable")
        return sum(self.values.pop(name, None) is not None for name in names)

    def ping(self) -> bool:
        if self.fail_ping:
            raise RedisConnectionError("redis unavailable")
        return True

    def close(self) -> None:
        return None


def profile(dataset_id: UUID | None = None, user_id: int = 42) -> CachedUserProfile:
    return CachedUserProfile(
        dataset_id=dataset_id or uuid4(),
        user_id=user_id,
        interests=("technology",),
        category_preferences=("technology",),
        age_group="25-34",
        country="US",
        device="mobile",
    )


def settings(**values: Any) -> Settings:
    return Settings(
        database_url=SecretStr("postgresql+psycopg://user:pass@localhost/adflow"),
        test_database_url=SecretStr("postgresql+psycopg://user:pass@localhost/adflow_test"),
        **values,
    )


def test_versioned_dataset_keys_and_json_round_trip_do_not_renew_expiration() -> None:
    redis = FakeRedis()
    item = profile()
    cache = RedisProfileCache(redis, randint=lambda low, high: 2)

    assert cache.key(item.dataset_id, item.user_id) == (
        f"adflow:{item.dataset_id}:profile:user-profile-v1:{item.user_id}"
    )
    assert cache.populate(item)
    key, payload, ttl = redis.set_calls[0]
    assert ttl == 58
    expiry_at = redis.expiry_at[key]
    assert expiry_at - redis.now == ttl
    hit = cache.get(item.dataset_id, item.user_id)
    assert hit.state == "hit"
    assert hit.profile == item
    assert redis.expiry_at[key] == expiry_at
    assert redis.set_calls == [(key, payload, 58)]


def test_health_reports_disabled_ready_and_degraded_without_changing_cache_counters() -> None:
    redis = FakeRedis()
    cache = RedisProfileCache(redis)
    assert cache.health() == "ready"
    redis.fail_ping = True
    assert cache.health() == "degraded"
    assert cache.metrics.snapshot()["hits"] == 0
    assert cache.metrics.snapshot()["misses"] == 0
    assert RedisProfileCache(None).health() == "disabled"


@pytest.mark.parametrize(
    "payload",
    [
        "{broken",
        '{"schema_version":"user-profile-v0"}',
        '{"schema_version":"user-profile-v1","dataset_id":"00000000-0000-0000-0000-000000000000","user_id":42,"interests":[],"category_preferences":[],"age_group":"x","country":"US","device":"mobile"}',
    ],
)
def test_invalid_json_version_or_identity_is_evicted_and_falls_through(payload: str) -> None:
    redis = FakeRedis()
    item = profile()
    cache = RedisProfileCache(redis)
    redis.values[cache.key(item.dataset_id, item.user_id)] = payload
    loaded: list[int] = []

    def load_profile() -> CachedUserProfile:
        loaded.append(item.user_id)
        return item

    result = cache.get_or_load(item.dataset_id, item.user_id, load_profile)

    assert result.state == "invalid"
    assert result.profile == item
    assert loaded == [item.user_id]
    assert len(redis.delete_calls) == 1
    assert len(redis.set_calls) == 1
    assert cache.metrics.snapshot()["invalid_payloads"] == 1


def test_miss_loads_profile_without_negative_caching_unknown_users() -> None:
    redis = FakeRedis()
    item = profile()
    cache = RedisProfileCache(redis)
    assert cache.get_or_load(item.dataset_id, item.user_id, lambda: item).state == "miss"
    assert cache.get_or_load(item.dataset_id, item.user_id, lambda: None).state == "hit"
    assert cache.get_or_load(item.dataset_id, 999, lambda: None).profile is None
    assert cache.key(item.dataset_id, 999) not in redis.values
    assert cache.metrics.snapshot()["hits"] == 1
    assert cache.metrics.snapshot()["misses"] == 2


def test_expired_entry_becomes_a_miss_and_is_reloaded() -> None:
    redis = FakeRedis()
    item = profile()
    cache = RedisProfileCache(redis, max_ttl_seconds=2, jitter_seconds=0)
    assert cache.populate(item)
    redis.now += 2
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.state == "miss"
    assert result.profile == item
    assert cache.metrics.snapshot()["misses"] == 1


def test_read_error_bypasses_all_remaining_redis_operations_for_that_load() -> None:
    redis = FakeRedis()
    redis.fail_get = True
    item = profile()
    cache = RedisProfileCache(redis)
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.state == "error"
    assert result.profile == item
    assert redis.set_calls == []
    assert redis.delete_calls == []
    assert cache.metrics.snapshot()["read_errors"] == 1
    assert cache.metrics.snapshot()["bypasses"] == {"read_error": 1}


def test_pool_exhaustion_has_its_own_bypass_reason() -> None:
    class ExhaustedRedis(FakeRedis):
        def get(self, name: str) -> str | None:
            raise RedisConnectionError("Too many connections")

    item = profile()
    cache = RedisProfileCache(ExhaustedRedis())
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.state == "error"
    assert result.reason == "pool_exhausted"
    assert cache.metrics.snapshot()["bypasses"] == {"pool_exhausted": 1}


def test_invalid_entry_with_failed_eviction_loads_database_and_skips_population() -> None:
    redis = FakeRedis()
    item = profile()
    cache = RedisProfileCache(redis)
    key = cache.key(item.dataset_id, item.user_id)
    redis.values[key] = "not-json"
    redis.fail_delete = True
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.profile == item
    assert result.reason == "invalidation_error"
    assert redis.set_calls == []
    assert cache.metrics.snapshot()["invalidation_errors"] == 1


def test_write_and_invalidation_errors_are_counted_without_losing_db_profile() -> None:
    redis = FakeRedis()
    redis.fail_set = True
    redis.fail_delete = True
    item = profile()
    cache = RedisProfileCache(redis)
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.profile == item
    assert result.state == "miss"
    assert not cache.invalidate(item.dataset_id, item.user_id)
    metrics = cache.metrics.snapshot()
    assert metrics["write_errors"] == 1
    assert metrics["invalidation_errors"] == 1
    assert metrics["bypasses"] == {"invalidation_error": 1, "write_error": 1}


def test_disabled_cache_is_bypass_and_hit_ratio_is_undefined_without_samples() -> None:
    cache = RedisProfileCache(None)
    item = profile()
    result = cache.get_or_load(item.dataset_id, item.user_id, lambda: item)
    assert result.state == "bypass"
    assert result.profile == item
    assert cache.metrics.snapshot()["hit_ratio"] is None
    assert cache.metrics.snapshot()["bypasses"] == {"disabled": 1}


def test_configuration_bounds_ttl_pool_and_timeouts() -> None:
    with pytest.raises(ValueError):
        RedisProfileCache(FakeRedis(), max_ttl_seconds=61)
    with pytest.raises(ValueError):
        RedisProfileCache(FakeRedis(), max_ttl_seconds=10, jitter_seconds=6)
    with pytest.raises(ValueError):
        settings(redis_url=SecretStr("http://redis:6379"))
    with pytest.raises(ValueError):
        settings(redis_profile_ttl_seconds=61)


def test_redis_pool_has_explicit_short_timeouts_zero_retries_and_bounded_exhaustion() -> None:
    cache = create_profile_cache(
        settings(
            redis_url=SecretStr("redis://localhost:6379/0"),
            redis_pool_max_connections=1,
        )
    )
    assert isinstance(cache.client, Redis)
    pool = cache.client.connection_pool
    assert isinstance(pool, ConnectionPool)
    assert pool.connection_kwargs["socket_connect_timeout"] == 0.1
    assert pool.connection_kwargs["socket_timeout"] == 0.1
    assert pool.connection_kwargs["retry"].get_retries() == 0

    class NoNetworkConnection(Connection):
        def connect(self) -> None:
            return None

    bounded_pool = ConnectionPool(connection_class=NoNetworkConnection, max_connections=1)
    connection = bounded_pool.get_connection()
    try:
        with pytest.raises(RedisConnectionError, match="Too many connections"):
            bounded_pool.get_connection()
    finally:
        bounded_pool.release(connection)
        bounded_pool.disconnect()
