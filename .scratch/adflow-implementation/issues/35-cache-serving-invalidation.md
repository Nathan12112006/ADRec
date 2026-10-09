# 35 — Integrate cache fallback and post-commit invalidation

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 33, 34

## Scope

Use cache-aside profile reads while retaining PostgreSQL authority for outcomes, events, experiments, current eligibility and bids. On a Redis read failure bypass remaining cache work for that request; failed cache writes cannot break otherwise valid database work.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [34 — Implement bounded Redis profile-cache access](34-profile-cache-adapter.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Commit profile changes before invalidation; document the accepted stale-repopulation race.
- [x] Dataset replacement pauses traffic and changes the cache namespace; no public profile-edit API is introduced.
- [x] Integration tests prove Redis outage preserves valid requests and database outage still returns 503.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implemented dataset-scoped profile cache-aside in recommendation serving. PostgreSQL supplies the dataset ID and remains authoritative; Redis hits provide only profile fields, while misses/read failures fall through to PostgreSQL. Added an internal profile-update service that commits before best-effort invalidation; no public edit route exists. README documents the accepted stale-repopulation race (maximum TTL 60 seconds) and pausing traffic/changing dataset ID for replacement.

Verification from `backend/` using isolated `adflow_gate33_test` (application URL `adflow_gate33_app`): `ADFLOW_RUN_POSTGRES_TESTS=1 python -m pytest tests/unit/test_profile_cache.py tests/unit/test_config.py tests/integration/test_profile_cache_serving.py tests/integration/test_http_lifecycle.py::test_real_database_unavailability_returns_safe_failures` — 44 passed. `python -m ruff check .`, `python -m ruff format --check .`, and `python -m mypy` — passed (114 source files). Redis outage integration confirms a valid request and durable replay; database outage returns 503. An initial assertion assumed a refused local Redis socket would be classified as a generic read error; redis-py observed the configured connect timeout, so the assertion now checks the documented timeout classification. Test fixtures append uniquely identified data; existing database history was preserved.
