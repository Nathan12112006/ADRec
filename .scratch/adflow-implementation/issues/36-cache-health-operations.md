# 36 — Expose dependency capabilities and disposable Redis configuration

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 33, 35

## Scope

Add Redis to Compose with 128MB LRU eviction and no persistence. Expose cache degradation and index/model capability status separately from database readiness.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [35 — Integrate cache fallback and post-commit invalidation](35-cache-serving-invalidation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Database readiness alone controls ready status; Redis outage reports degradation without failing readiness.
- [x] Index fallback and unavailable V2 model have the accepted distinct behavior.
- [x] Document cache controls, timeout limitations, counters and hit ratio h/(h+m), null when no eligible observations.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Compose now runs digest-pinned Redis 8.0.2 with maxmemory 128 MB, `allkeys-lru`, RDB/AOF disabled, a 192 MB container cap, and a healthcheck. The API readiness response still returns 503 only for PostgreSQL failure; it reports Redis `degraded` separately and exposes process-lifetime cache counters and hit ratio. It reports exact fallback vs Flat/HNSW index and V1/V2 model capability separately. README documents memory/timeout controls, disposable recovery, and metric semantics.

Redis is bound to loopback port 6379 for local development and cache comparisons; it is not published on external interfaces.

Verification: `docker compose config --quiet` passed. Live `adflow-redis-1` was healthy; `CONFIG GET maxmemory maxmemory-policy save appendonly` returned 134217728 bytes, `allkeys-lru`, no RDB save schedule, and `appendonly no`; container memory cap is 201326592 bytes. From `backend/`, focused cache/HTTP/PostgreSQL run: `ADFLOW_RUN_POSTGRES_TESTS=1 python -m pytest tests/unit/test_http.py tests/unit/test_profile_cache.py tests/integration/test_profile_cache_serving.py tests/integration/test_http_lifecycle.py::test_real_database_unavailability_returns_safe_failures` — 48 passed. Ruff check/format and mypy passed (114 source files). The integration health assertion confirmed Redis outage is degraded while readiness remains ready, exact fallback is reported, and V2 capability is unavailable without a model. Existing retrieval and CTR serving tests encode their separate runtime behavior. Test fixtures append unique datasets; preserved existing data.
