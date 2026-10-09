# 37 — Measure profile-cache behavior under reproducible access patterns

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 33, 35, 36

## Scope

Run focused cold/warm and uniform/hot-user cache comparisons with fixed data, ranking and retrieval settings. Record actual cache counters, elapsed time and outage behavior; this is component evidence before the full load-test phase.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [35 — Integrate cache fallback and post-commit invalidation](35-cache-serving-invalidation.md)
- [36 — Expose dependency capabilities and disposable Redis configuration](36-cache-health-operations.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Explicitly reset cold cache and describe how warm cache was populated.
- [x] Include provenance, database read reduction and failed-cache fallback checks.
- [x] Do not claim whole-service speedup from component timing; document observed limitations.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Added the reproducible component runner `backend/scripts/profile_cache_comparison.py` and README command. It uses the first 50 users from application dataset `45db186a-f06e-5005-99fe-3a5c1904beb2`; each cold pass deletes only the selected users' exact dataset-scoped Redis keys. The next pass is warm because the cold pass populated valid profiles. Redis 8.0.2, 60-second TTL, PostgreSQL 18.6, Windows host Python 3.10.11. Timed 500 operations per pattern, one observation each:

| Access pattern | Mode | Elapsed ms | Profile-row queries |
| --- | --- | ---: | ---: |
| Uniform (50 users) | PostgreSQL | 3383.758 | 500 |
| Uniform (50 users) | Cold cache | 1352.112 | 50 |
| Uniform (50 users) | Warm cache | 936.098 | 0 |
| Hot user (1 user) | PostgreSQL | 3242.548 | 500 |
| Hot user (1 user) | Cold cache | 920.000 | 1 |
| Hot user (1 user) | Warm cache | 885.917 | 0 |

Cache metrics for the paired cache runs: 1,949 hits, 51 misses, 0 invalid payloads/errors, hit ratio 0.9745. The miss totals are 50 uniform plus 1 hot-user; warm passes had no profile-row reads. The acceptance outage/replay check is `test_redis_outage_falls_through_and_replay_stays_durable`: Redis connect timeout fell through to PostgreSQL, returned a valid recommendation, and replay returned the durable saved result; focused integration suite passed. Verification: from `backend/`, `python scripts/profile_cache_comparison.py` produced the recorded values; Ruff check/format and mypy passed (114 app/test sources plus the runner).

These are single-run component timings on a small local dataset, not an API benchmark or evidence of whole-service speedup. Retrieval/ranking, the required per-request PostgreSQL dataset-ID lookup, HTTP overhead, contention, repeated-run variation, and production-scale locality are outside this script. The measured profile-row reduction does not eliminate all PostgreSQL work. Do not extrapolate the observed timings beyond this run.
