# 07 — Expose lifecycle APIs with health checks and structured errors

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 01, 05, 06

## Scope

Add thin Pydantic/FastAPI routes for POST recommendations and impression/click events, GET /health/live and /health/ready. Enforce Idempotency-Key and input validation; standardize 200/204/404/409/410/422/503 responses. Add structured request/selection logging and stage timing hooks without a telemetry platform.

## Dependencies

- [01 — Create the backend package and configuration foundation](01-backend-foundation.md)
- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)
- [06 — Record client impressions and clicks with atomic accounting](06-event-workflow.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] TestClient verifies response schemas, empty 204 bodies, identifiers, validation and error mapping.
- [x] Liveness survives DB loss; readiness reports it; responses never expose stack traces/credentials.
- [x] Logs include request/selection context and durations; baseline probability remains absent/null.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented by Codex. Added `backend/app/api/routes.py`, `backend/app/schemas/lifecycle.py` and package initialization, `backend/app/core/observability.py`, `backend/tests/unit/test_http.py`, and `backend/tests/integration/test_http_lifecycle.py`. Updated `app/main.py` to register routes, safe exception adapters, request identity and logging middleware; added a selection timing hook in `services/recommendations.py`. Updated README setup, executable default-seed HTTP walkthrough, response/error contracts, module boundaries, logging/timing semantics and focused check commands.

The three POST endpoints call existing services with no duplicate persistence logic. Positive strict signed-64-bit user IDs, UUID recommendation IDs, forbidden extra payload fields and one required nonblank Idempotency-Key (maximum 255 characters) are validated. Keys retain their exact identity. Recommendation responses contain saved selection context, decimal bid and explicit null predicted CTR; events contain server-derived attribution and decimal simulated revenue. No-ad outcomes return bodyless 204. Workflow 404/409/410/422/503 errors use a consistent error envelope. Validation inputs and raw database/exception strings are never echoed. Unexpected failures return safe 500. OpenAPI describes lifecycle responses and errors.

Liveness performs no database work; readiness uses bounded `SELECT 1`, without implicit migration checks. Every response gets a server-generated X-Request-ID. JSON application logs include route template, method, status, total duration and validated selection/event context; request keys appear only as SHA-256 digests. Logs exclude raw payloads, query strings, credentials and exception text. Fixed request-local hooks measure selection, recommendation/event workflow including commit, and readiness probes. Replays skip selection. No global metric history or telemetry subsystem was introduced. Adapter work is constant apart from bounded request-key hashing/serialization; existing selection scan costs remain unchanged. Total timing ends at response-header preparation, not client receipt.

Thirty new unit HTTP cases cover response schemas, ID/header/body validation, duplicate headers, null probability, empty 204, documented statuses, safe unexpected/SQLAlchemy failures, request IDs, structured logs and liveness/readiness during connection refusal. Four PostgreSQL HTTP tests verify actual recommendation replay, click-before-impression recovery, duplicate-event accounting directly in persistence, no-ad replay, unknown IDs, key ownership, expiry/accepted duplicate behavior, reachable readiness and required storage failure through all endpoints. Logs prove selection timing on creation, its absence on replay, and context isolation across requests. Existing lifecycle race/transaction tests remain passing.

Runtime: Windows CPython 3.10.11, pytest 9.1.1, PostgreSQL 18.6; no dependency, lock or schema changes. Checked official FastAPI error-handler and response-status documentation (linked in README). Reused repository-local portable PostgreSQL on 127.0.0.1:15432, creating only `adflow_ticket07_test`. Application target `adflow_ticket03_dev` was configured but never modified. Test fixtures append unique datasets without deleting durable history. Integration setup migrated the fresh test database through Alembic. Windows TestClient hung inside the sandbox; stopped that run and used reviewed outside-sandbox execution successfully. No unresolved approval rejection occurred.

Executed from repository root:

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -l '.local-postgres/server.log' -o '-h 127.0.0.1 -p 15432' start
& '.local-postgres/pgsql/bin/createdb.exe' -h 127.0.0.1 -p 15432 -U adflow adflow_ticket07_test
```

Executed from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_http.py -q --tb=short
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket07_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_http_lifecycle.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Results: focused unit suite **30 passed in 4.17s**, focused PostgreSQL HTTP suite **4 passed in 1.76s**, full regression **158 passed in 18.69s** (74 unit, 84 integration). Strict mypy passed for 43 files; Ruff lint and format checks passed for 43 files. Alembic reported **No new upgrade operations detected**. Initial formatting/type annotation issues were corrected before these final checks. Repository-root `git diff --check` passed after removing an extra ticket EOF blank line.

Stopped the disposable server successfully using repository-root `& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -m fast stop`. Docker packaging and full Phase 1 gate remain tickets 09/10. This ticket records technical API implementation, not the human learning checkpoint.
