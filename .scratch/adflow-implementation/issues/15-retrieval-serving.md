# 15 — Integrate candidate retrieval into recommendation serving

Status: ready-for-agent
State: active
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 07, 10, 13, 14

## Scope

Replace the baseline all-ad selection input with the bounded retrieved candidate set, preserving ranking semantics, durable replay and no-ad behavior. Persist retrieval context with the selection and separate vector/metadata/ranking/database timings.

## Dependencies

- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [13 — Implement current eligibility filtering and exact fallback](13-eligibility-backfill.md)
- [14 — Add the HNSW candidate-retrieval comparison](14-hnsw-option.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] End-to-end tests prove downstream ranking uses at most the configured candidate count.
- [ ] Replay never reretrieves; index/model-independent baseline serving and exact fallback work.
- [ ] Snapshot/eligibility changes cannot save stale eligibility or mismatched score/bid fields.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-08

Nathan confirmed the public recommendation service/HTTP API with real FAISS and isolated PostgreSQL, persisted selection context and request timings as test seams. Implemented with the implement and TDD skills. Baseline for review: `8eb6608806a75dd51c4eb608b87107bc4d43b2d1`.

The recommendation service now retrieves at most the configured candidate limit, then applies the existing distinct-overlap/bid/ID selector only to those candidates. Optional process-local ActiveSnapshot loading is configured by ADFLOW_RETRIEVAL_INDEX_PATH; absent/empty configuration uses exact current-inventory fallback. Flat remains the initial index default; explicitly supplied HNSW artifacts use their persisted settings without claiming promotion. Startup never builds artifacts. Missing/corrupt/incompatible artifacts retain fallback diagnostics. Each worker must load its own complete replacement; no watcher or reload endpoint was introduced.

New selection JSON retains compact retrieval provenance (mode, index/vector/vocabulary identity, requested/returned counts, fallback reason, counters and timings), without candidate payloads. Old saved selections without this field remain valid with null context. Key replay precedes inventory/retrieval and preserves the saved result. Winner revalidation now also checks category/advertiser identity, alongside bid/interests/eligibility, under the existing share locks and bounded retry. No schema, dependency, accounting or CTR changes. Lifecycle database queries/flush/commit are timed separately from vector/metadata/fallback and ranking; retrieval's own database work remains included in its metadata/fallback timers. Nested timers are documented, not summed as disjoint costs.

Updated files: recommendation service, application startup/settings and HTTP route, .env.example/Compose path wiring, README workflow/setup/timing guidance, new retrieval-serving integration tests, existing recommendation race and HTTP adapter tests. The existing independent-opportunity event test now compares selection fields excluding retrieval measurements, which legitimately differ between opportunities.

TDD evidence: first serving test failed on absent candidate_limit argument, then passed with bounded retrieval; HTTP test expected exact mode but observed exact_fallback before snapshot/configuration wiring, then passed; timing/replay test lacked database_ms before query/flush/commit instrumentation, then passed. Focused suite: 52 passed (serving/recommendations/HTTP adapter); later Flat/HNSW/fallback/no-ad/timing/race suite: 29 passed. First full suite: 398 passed, 1 failed because an older event test compared distinct opportunities' newly added timings; corrected as described above. Final full regression and independent review are pending below.

No benchmark or 100,000-ad scale claim. These new fixtures contain 2–5 ads. Exact fallback can still scan all eligible inventory; downstream ranking is O(C) plus interest processing for at most configured C. Immutable artifact validation is at startup/reload, never synchronous rebuilding in a request. Required database failures still return safe 503 and rollback.

#### Exact verification commands

PowerShell from repository root (local PostgreSQL was stopped; existing databases were preserved; created one separate test database):

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket15_test
docker compose config --quiet
git diff --check
```

Native checks from `backend/`, outside the sandbox for PostgreSQL/FAISS access:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket15_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_retrieval_serving.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/integration/test_retrieval_serving.py tests/integration/test_recommendations.py tests/unit/test_http.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/integration/test_retrieval_serving.py tests/integration/test_recommendations.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

The initial sandbox run could not connect to PostgreSQL; a subsequent outside-sandbox attempt using adflow_test found that database absent. Neither failure demonstrated an application defect. Local ticket-specific database selection resolved setup. Compose configuration validation passed; no Docker image rebuild or container startup is claimed for this ticket. Native HTTP startup with persisted Flat/HNSW and failure artifacts is covered by TestClient tests. Artifacts are generated under pytest temporary directories and use per-test dataset UUIDs; no fixed production artifact was changed.
