# 06 — Record client impressions and clicks with atomic accounting

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02, 05

## Scope

Implement impression/click services by recommendation ID. Derive attribution server-side; require impression before first click; accept first events strictly within the creation-based 24-hour window. Deduplicate before expiry rejection and credit the captured bid once per first accepted click.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)
- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Concurrent duplicates produce one impression/click and one decimal revenue credit.
- [x] Click-before-impression can recover via confirmation/retry; accepted duplicates remain safe after expiry.
- [x] Bid edits/deactivation do not rewrite existing attribution; failed commits accept no event/accounting effect.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented in `cee3fcc`, relative to pre-ticket commit `52ede4ca5edd2465dda7187626e5be83c70eb7cd`. Parallel code-review used `git diff 52ede4ca5edd2465dda7187626e5be83c70eb7cd...HEAD` at that implementation commit. Standards: zero actionable findings. Spec: zero actionable findings; all ticket 06 requirements satisfied. No review-driven changes were needed.

Added `backend/app/services/events.py`: public `record_event(session, recommendation_id, event_type, clock=...)`, typed impression/click inputs and immutable `EventResult`. The service owns its transaction and returns only after commit. Attribution comes from the saved recommendation's user/ad IDs and bid, never client claims or current inventory. First impressions store zero revenue; first clicks store the captured decimal bid in the same event row, making acceptance/accounting one atomic insert. Zero bids remain accepted. Existing accepted events replay their original timestamp/revenue before any expiry/order check. First events at or after recommendation creation plus 24 hours return 410; a missing impression before an otherwise eligible first click returns retryable 409 `impression_required`; unknown recommendation returns 404. SQLAlchemy read/write/commit/pool/lock failures translate to safe 503 without raw database details.

PostgreSQL's `(recommendation_id, event_type)` primary key and targeted `INSERT ... ON CONFLICT ... DO NOTHING` arbitrate concurrent delivery. After a conflicting insert waits, a new READ COMMITTED lookup obtains the committed winner. No mutable revenue counter, event update, application-only uniqueness guard or attribution revalidation against current ads is used. An in-flight impression not yet committed can cause a concurrent click to return 409; confirm then retry. Failed insert or commit leaves no accepted row and no revenue. Response-loss retries use the same event identity. Other database errors are not treated as successful duplicates.

Added `backend/app/core/clock.py` and moved the existing recommendation UTC clock there so event/recommendation workflows share time without depending on each other. Event receipt time is captured once before database work; clock injection is a server-side test seam, not a client backdating field. No schema, migration or dependency changes. HTTP adapters remain ticket 07.

Nathan explicitly confirmed the public event-service/PostgreSQL test seam. Added `backend/tests/integration/test_events.py`, using generated unique datasets and actual recommendations. TDD evidence: first test failed to import the absent event module; click-before-impression test failed before ordering/accounting logic; duplicate tests exposed PostgreSQL unique violations before replay support; strict expiry/unknown-identity cases failed before 410/404 checks; concurrent clicks exposed a real unique violation before targeted conflict handling; insert/commit/unavailable-database tests raised raw database errors before 503 translation. Each behavior slice passed after implementation. Two intermediate test/source syntax errors and initial Ruff import/line-length checks were corrected before final checks.

Focused suite covers 23 cases: display confirmation/committed return/server attribution, click-before-impression recovery, accepted impression/click duplicates before and after expiry, first events one microsecond before/exactly at/one microsecond after expiry, unknown recommendations, eight simultaneous duplicate deliveries per event type with persisted count/revenue assertions, bid/ad/advertiser edits after selection, immediate insert and deferred commit failure for both event types with successful retry, unavailable database, zero-bid clicks and independent opportunities for the same ad. Rejected/failed event persistence and decimal revenue are checked at the PostgreSQL boundary. Failure triggers apply only to unique fixture recommendations/event types and are removed in `finally`. No durable-history deletion or database reset occurs; integration tests run serially.

README documents the public service/result, 404/409/410/503 behavior, clock/receipt semantics, concurrency and commit guarantees, focused checks, accounting and limitations. A constant number of indexed recommendation/event reads and at most one insert gives O(1) application working space; database index maintenance and contention add cost. Event history grows with accepted interactions; no pruning or throughput claim is introduced. Conflict behavior was checked against official SQLAlchemy 2.0.54 PostgreSQL dialect and PostgreSQL 18 INSERT documentation linked in README.

Runtime: Windows CPython 3.10.11, pytest 9.1.1, PostgreSQL 18.6, existing locked SQLAlchemy 2.0.54 and psycopg 3.3.6. Reused the ignored portable local cluster on localhost:15432; created only new isolated database `adflow_ticket06_test`, explicitly migrated before implementation and checked again at completion. Application target `adflow_ticket03_dev` was configured but never modified. Random missing database names intentionally exercise connection failure. Database/TestClient and Git-index operations required reviewed outside-sandbox execution; no unresolved approval rejection occurred.

Executed from repository root (server restarted after explicit seam confirmation):

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -l '.local-postgres/server.log' -o '-h 127.0.0.1 -p 15432' start
& '.local-postgres/pgsql/bin/createdb.exe' -h 127.0.0.1 -p 15432 -U adflow adflow_ticket06_test
```

Executed from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket06_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m alembic -x database=test upgrade head
.\.venv\Scripts\python.exe -m pytest tests/integration/test_events.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Results: focused event suite **23 passed in 1.88 seconds**. Final full suite after shared-clock extraction **124 passed in 15.24 seconds** (44 unit, 80 PostgreSQL integration). Strict mypy succeeded for 37 source files; Ruff lint/format passed (37 files). Alembic: **No new upgrade operations detected**. Repository-root `git diff --check` passed. This ticket implements technical behavior, not the later human explanation checkpoint.

Stopped the disposable server successfully after verification/review with repository-root command `& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -m fast stop`. Ignored runtime/data are retained for later checks.
