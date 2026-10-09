# 38 — Verify and record the Redis phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 33, 37

## Scope

Run cache correctness, outage and health regressions and record the measured comparison and operating instructions.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [37 — Measure profile-cache behavior under reproducible access patterns](37-cache-comparison.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Expiry, invalidation, namespace replacement and outage behavior match the contract.
- [x] Preserve PostgreSQL accounting and experiment regressions.
- [x] Offer the cache/performance learning checkpoint and unlock Phase 7 after technical verification.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Phase 6 technical gate passed. From `backend/`, using `adflow_gate33_test` and app data in `adflow_gate33_app`, ran cache unit/HTTP/model/ranking and PostgreSQL cache-serving, event, ranked-recommendation, experiment-results and HTTP lifecycle regressions: `ADFLOW_RUN_POSTGRES_TESTS=1 python -m pytest tests/unit/test_profile_cache.py tests/unit/test_http.py tests/unit/test_ctr_serving.py tests/unit/test_ranking_strategies.py tests/integration/test_profile_cache_serving.py tests/integration/test_events.py tests/integration/test_ranked_recommendations.py tests/integration/test_experiment_results.py tests/integration/test_http_lifecycle.py` — 142 passed in 38.57s. The run initially identified the expected expanded readiness contract in one lifecycle assertion; after updating it, the complete suite passed. Ruff check/format and mypy passed (114 app/test sources plus the cache comparison runner).

Phase 6 comparison evidence is in [ticket 37](37-cache-comparison.md), with a repeatable runner and operating instructions in README. Redis 8.0.2 is healthy, loopback-only, capped at 128 MB with LRU eviction and persistence disabled. Database readiness remains independent from Redis; health reports exact fallback vs Flat/HNSW and V1/V2 model capability. Ticket [62 — Explain and modify caching and performance measurement](62-learning-cache-performance.md) remains a separate human checkpoint with its existing ticket 51 dependency; this technical gate does not certify learning. Phase 7 is unlocked.
