"""Versioned, bounded Redis cache-aside primitives for synthetic-user profiles."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from random import Random
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from redis import Redis
from redis.backoff import NoBackoff
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry

from app.core.config import Settings

PROFILE_SCHEMA_VERSION = "user-profile-v1"
MAX_PROFILE_TTL_SECONDS = 60
PROFILE_TTL_JITTER_SECONDS = 5


class CachedUserProfile(BaseModel):
    """Typed payload required by candidate retrieval and ranking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["user-profile-v1"] = "user-profile-v1"
    dataset_id: UUID
    user_id: int = Field(gt=0, le=9223372036854775807)
    interests: tuple[str, ...]
    category_preferences: tuple[str, ...]
    age_group: str
    country: str
    device: str


class RedisProfileClient(Protocol):
    """Small synchronous Redis surface used by the adapter and deterministic tests."""

    def get(self, name: str) -> Any: ...

    def set(self, name: str, value: str, *, ex: int) -> Any: ...

    def delete(self, *names: str) -> Any: ...

    def ping(self) -> Any: ...

    def close(self) -> Any: ...


CacheState = Literal["hit", "miss", "invalid", "error", "bypass"]


def _failure_reason(error: RedisError, operation: str) -> str:
    if isinstance(error, RedisConnectionError) and str(error).lower() == "too many connections":
        return "pool_exhausted"
    if isinstance(error, RedisTimeoutError):
        return f"{operation}_timeout"
    return f"{operation}_error"


@dataclass(frozen=True)
class CacheLookup:
    state: CacheState
    profile: CachedUserProfile | None = None
    reason: str | None = None


class ProfileCacheMetrics:
    """Lock-protected process counters; Redis is never needed to report failures."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()
        self._errors: Counter[str] = Counter()
        self._bypasses: Counter[str] = Counter()

    def increment(self, name: str) -> None:
        with self._lock:
            self._counts[name] += 1

    def error(self, operation: str) -> None:
        with self._lock:
            self._errors[operation] += 1

    def bypass(self, reason: str) -> None:
        with self._lock:
            self._bypasses[reason] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            hits = counts.get("hits", 0)
            misses = counts.get("misses", 0)
            denominator = hits + misses
            return {
                "hits": hits,
                "misses": misses,
                "invalid_payloads": counts.get("invalid_payloads", 0),
                "read_errors": self._errors.get("read", 0),
                "write_errors": self._errors.get("write", 0),
                "invalidation_errors": self._errors.get("invalidate", 0),
                "hit_ratio": hits / denominator if denominator else None,
                "bypasses": dict(sorted(self._bypasses.items())),
            }


class RedisProfileCache:
    """Cache one validated profile per dataset namespace; callers retain DB authority."""

    def __init__(
        self,
        client: RedisProfileClient | None,
        *,
        max_ttl_seconds: int = MAX_PROFILE_TTL_SECONDS,
        jitter_seconds: int = PROFILE_TTL_JITTER_SECONDS,
        randint: Callable[[int, int], int] | None = None,
        metrics: ProfileCacheMetrics | None = None,
    ) -> None:
        if not 1 <= max_ttl_seconds <= MAX_PROFILE_TTL_SECONDS:
            raise ValueError("profile TTL must be between 1 and 60 seconds")
        if not 0 <= jitter_seconds <= PROFILE_TTL_JITTER_SECONDS:
            raise ValueError("profile TTL jitter must be between 0 and 5 seconds")
        self._client = client
        self._max_ttl = max_ttl_seconds
        self._jitter = min(jitter_seconds, max_ttl_seconds - 1)
        self._randint = randint or Random().randint
        self.metrics = metrics or ProfileCacheMetrics()

    @property
    def client(self) -> RedisProfileClient | None:
        return self._client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def health(self) -> Literal["disabled", "ready", "degraded"]:
        """Probe Redis with the client's configured socket bounds; never affect readiness."""
        if self._client is None:
            return "disabled"
        try:
            return "ready" if self._client.ping() else "degraded"
        except RedisError:
            return "degraded"

    @staticmethod
    def key(dataset_id: UUID, user_id: int) -> str:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        return f"adflow:{dataset_id}:profile:{PROFILE_SCHEMA_VERSION}:{user_id}"

    def get(self, dataset_id: UUID, user_id: int) -> CacheLookup:
        key = self.key(dataset_id, user_id)
        if self._client is None:
            self.metrics.bypass("disabled")
            return CacheLookup("bypass", reason="disabled")
        try:
            payload = self._client.get(key)
        except RedisError as error:
            reason = _failure_reason(error, "read")
            self.metrics.error("read")
            self.metrics.bypass(reason)
            return CacheLookup("error", reason=reason)
        if payload is None:
            self.metrics.increment("misses")
            return CacheLookup("miss")
        try:
            profile = CachedUserProfile.model_validate_json(payload)
            if profile.dataset_id != dataset_id or profile.user_id != user_id:
                raise ValueError("cached profile identity mismatch")
        except (ValidationError, ValueError, TypeError):
            self.metrics.increment("invalid_payloads")
            try:
                self._client.delete(key)
            except RedisError as error:
                reason = _failure_reason(error, "invalidation")
                self.metrics.error("invalidate")
                self.metrics.bypass(reason)
                return CacheLookup("invalid", reason=reason)
            return CacheLookup("invalid", reason="invalid_payload")
        self.metrics.increment("hits")
        return CacheLookup("hit", profile=profile)

    def get_or_load(
        self,
        dataset_id: UUID,
        user_id: int,
        loader: Callable[[], CachedUserProfile | None],
    ) -> CacheLookup:
        """Return a hit or load PostgreSQL once; unknown users are never cached."""
        result = self.get(dataset_id, user_id)
        if result.state == "hit":
            return result
        profile = loader()
        if profile is not None:
            if profile.dataset_id != dataset_id or profile.user_id != user_id:
                raise ValueError("profile loader returned a different user or dataset")
            if result.state == "miss" or (
                result.state == "invalid" and result.reason == "invalid_payload"
            ):
                self.populate(profile)
        return CacheLookup(result.state, profile=profile, reason=result.reason)

    def populate(self, profile: CachedUserProfile) -> bool:
        if self._client is None:
            self.metrics.bypass("disabled")
            return False
        ttl = self._max_ttl - self._randint(0, self._jitter) if self._jitter else self._max_ttl
        try:
            stored = self._client.set(
                self.key(profile.dataset_id, profile.user_id), profile.model_dump_json(), ex=ttl
            )
            return bool(stored)
        except RedisError as error:
            self.metrics.error("write")
            self.metrics.bypass(_failure_reason(error, "write"))
            return False

    def invalidate(self, dataset_id: UUID, user_id: int) -> bool:
        if self._client is None:
            self.metrics.bypass("disabled")
            return False
        try:
            self._client.delete(self.key(dataset_id, user_id))
            return True
        except RedisError as error:
            self.metrics.error("invalidate")
            self.metrics.bypass(_failure_reason(error, "invalidation"))
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except RedisError:
                self.metrics.error("close")


def create_profile_cache(settings: Settings) -> RedisProfileCache:
    """Create one process-shared bounded pool; no network call occurs at construction."""
    if settings.redis_url is None:
        return RedisProfileCache(None, max_ttl_seconds=settings.redis_profile_ttl_seconds)
    pool = ConnectionPool.from_url(
        settings.redis_url.get_secret_value(),
        max_connections=settings.redis_pool_max_connections,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
        retry=Retry(NoBackoff(), 0),
        retry_on_timeout=False,
        retry_on_error=[],
    )
    client = Redis(connection_pool=pool)
    return RedisProfileCache(client, max_ttl_seconds=settings.redis_profile_ttl_seconds)
