# 34 — Implement bounded Redis profile-cache access

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 33

## Scope

Cache versioned user-profile JSON only, with schema validation, dataset namespaces, atomic expiry and downward jitter from a maximum 60-second TTL. Use a shared bounded connection pool, short 100ms connect/socket timeouts and zero automatic retries.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Malformed, stale-version and absent entries fall through to PostgreSQL; misses are not negatively cached.
- [x] Cache hits do not renew expiry; tests exercise expiry, serialization and pool exhaustion.
- [x] Cache telemetry distinguishes hits, misses, invalid entries, errors and bypasses.

## Comments

Added `app.cache.profiles`: typed `user-profile-v1` JSON profiles; dataset-scoped versioned keys; cache outcomes for hit, miss, invalid payload, read error, and disabled bypass; loader fallback; best-effort invalid eviction; no negative caching; and population only after a valid profile load. Redis read failures skip remaining Redis work for that lookup. Writes use one `SET` with `EX` and downward jitter, capped at the configured maximum TTL (default 60 seconds). Hits issue no write or expiry command. Pool exhaustion, timeouts and operation failures are surfaced to separate process-local counters and bypass reasons. The adapter includes post-commit invalidation and close methods for the serving lifecycle integration in ticket 35.

Added optional Redis settings (`REDIS_URL`, pool max 8, 100 ms connect/socket timeouts, profile TTL max 60 seconds) and pinned `redis==8.1.0` in `pyproject.toml`/`uv.lock`. Redis is disabled when no URL is configured. The connection pool is process-shared by the adapter instance, bounded to 1–64, uses explicit zero retries, and raises on exhaustion. README and `.env.example` document settings and the ticket 35 boundary. Version-sensitive defaults were checked against redis-py 8.1.0's [connection documentation](https://redis.readthedocs.io/en/stable/connections.html) and [retry documentation](https://redis.readthedocs.io/en/stable/retry.html); those docs specify a three-retry default from redis-py 6 and bounded-pool exhaustion behavior.

Verification from `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_profile_cache.py tests/unit/test_config.py -q
.venv/Scripts/python.exe -m mypy
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```

Results: 40 tests passed; mypy checked 112 source files; Ruff lint and formatting passed. Tests cover JSON round-trip, dataset namespace/identity, stale schema and malformed data, expiry/no renewal, unknown-user no-negative-cache, read/write/invalidation errors, bypass metrics, explicit retry/timeout/pool configuration, and pool exhaustion. A disposable Redis 8.0.2 smoke test stored a 2-second entry atomically, observed a TTL of 1 after a hit 1.1 seconds later, and then observed a miss after expiration. Its counters were one hit and one miss. No PostgreSQL serving path is integrated in this ticket; ticket 35 wires the adapter into recommendation transactions and invalidation.
