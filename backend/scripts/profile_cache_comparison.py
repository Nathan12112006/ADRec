"""Compare PostgreSQL profile reads with cold/warm Redis cache-aside component runs.

Run from backend/ with ADFLOW_DATABASE_URL, ADFLOW_TEST_DATABASE_URL, and
ADFLOW_REDIS_URL configured. Only selected dataset-scoped cache keys are deleted.
This measures profile access only; it does not benchmark recommendation serving.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from time import perf_counter

from sqlalchemy import select

from app.cache.profiles import CachedUserProfile, create_profile_cache
from app.core.config import load_settings
from app.db.session import Database
from app.models.records import User


def profile_from_user(user: User) -> CachedUserProfile:
    return CachedUserProfile(
        dataset_id=user.dataset_id,
        user_id=user.id,
        interests=tuple(user.interests),
        category_preferences=tuple(user.category_preferences),
        age_group=user.age_group,
        country=user.country,
        device=user.device,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operations", type=int, default=500)
    count = parser.parse_args().operations
    if count < 1:
        parser.error("--operations must be positive")

    settings = load_settings()
    if settings.redis_url is None:
        parser.error("ADFLOW_REDIS_URL must point at the disposable Redis service")
    database = Database(settings)
    cache = create_profile_cache(settings)
    profile_reads = 0
    try:
        with database.session() as session:
            rows = session.scalars(select(User).order_by(User.id).limit(50)).all()
            profiles = [profile_from_user(user) for user in rows]
        if not profiles:
            parser.error("the application database has no synthetic users")
        profile_by_id = {profile.user_id: profile for profile in profiles}
        redis = cache.client
        if redis is None or cache.health() != "ready":
            parser.error("configured Redis is not reachable")

        def loader(user_id: int) -> Callable[[], CachedUserProfile | None]:
            def load() -> CachedUserProfile | None:
                nonlocal profile_reads
                profile_reads += 1
                with database.session() as session:
                    user = session.scalar(select(User).where(User.id == user_id))
                    return profile_from_user(user) if user is not None else None

            return load

        def measure(
            label: str, user_ids: list[int], *, use_cache: bool
        ) -> dict[str, int | float | str]:
            before = profile_reads
            started = perf_counter()
            for user_id in user_ids:
                if use_cache:
                    profile = profile_by_id[user_id]
                    lookup = cache.get_or_load(profile.dataset_id, user_id, loader(user_id))
                    if lookup.profile != profile:
                        raise RuntimeError("database/cache profile mismatch")
                elif loader(user_id)() != profile_by_id[user_id]:
                    raise RuntimeError("database profile mismatch")
            return {
                "label": label,
                "operations": len(user_ids),
                "elapsed_ms": round((perf_counter() - started) * 1000, 3),
                "profile_row_queries": profile_reads - before,
            }

        results: list[dict[str, int | float | str]] = []
        patterns = {
            "uniform": [profiles[index % len(profiles)].user_id for index in range(count)],
            "hot_user": [profiles[0].user_id] * count,
        }
        for label, user_ids in patterns.items():
            for user_id in set(user_ids):
                profile = profile_by_id[user_id]
                redis.delete(cache.key(profile.dataset_id, user_id))
            results.append(measure(f"{label}_database", user_ids, use_cache=False))
            results.append(measure(f"{label}_cold", user_ids, use_cache=True))
            results.append(measure(f"{label}_warm", user_ids, use_cache=True))

        print(
            json.dumps(
                {
                    "dataset_id": str(profiles[0].dataset_id),
                    "profile_count": len(profiles),
                    "redis_ttl_seconds": settings.redis_profile_ttl_seconds,
                    "results": results,
                    "cache_metrics": cache.metrics.snapshot(),
                },
                sort_keys=True,
            )
        )
    finally:
        cache.close()
        database.dispose()


if __name__ == "__main__":
    main()
