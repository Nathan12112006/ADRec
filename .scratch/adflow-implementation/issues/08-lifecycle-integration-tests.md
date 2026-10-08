# 08 — Verify lifecycle races, expiration and dependency failures

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 03, 07

## Scope

Build isolated PostgreSQL integration fixtures and controllable-clock/concurrency scenarios. Exercise the complete lifecycle beyond unit-level prechecks, including response-loss replay, no-ad replay, mismatched keys/users, inactive inventory, unknown IDs and commit failure.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Real PostgreSQL tests cover racing keys/events and exact 24-hour boundaries including duplicates after expiry.
- [x] Changed bids/eligibility and click ordering retain coherent saved state.
- [x] Test execution cannot reset the development database; commands and observed results are retained.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented by Codex using the implement/TDD skills. Nathan confirmed the HTTP + isolated PostgreSQL seam, direct persistence count/revenue assertions, controllable server-clock dependency, and review/commit of both tickets 07 and 08 against `b95748da55befabf791a9302c29dea287116a2a2`. Ticket 07's existing working changes were preserved and included with his confirmation.

Added `backend/tests/integration/test_http_resilience.py` with 28 real PostgreSQL HTTP scenarios. Its fixture runs production app lifespan/session dependencies with the application URL set explicitly to TEST_DATABASE_URL and the companion setting pointing to a random unused database; neither URL targets development. Only server time is overridden. Every fixture gets a unique synthetic dataset and request identities. No reset/delete/truncate operations are introduced. Existing opt-in integration setup explicitly migrates the separate test URL; session cleanup and application lifespan dispose their own pools.

Added `get_clock` in `backend/app/api/dependencies.py` and passed that callable through all three lifecycle routes into the existing services. Production defaults to the shared UTC clock; clients cannot send timestamps. Updated the earlier HTTP adapter test doubles to accept the existing services' clock keyword. No schema, lock, dependency or monetary accounting implementation changed. README records the new test command, safety boundaries, synchronization/failure mechanisms and timing seam.

TDD evidence: first test collection failed because the clock dependency did not exist. After adding the provider alone, all three request expiry cases failed because routes ignored controlled time. Passing the clock into recommendation serving made them pass. The next six first-event cases failed on timestamps/expiry before the event routes forwarded the same clock, then passed. Remaining characterization checks exercise already implemented workflow guarantees and passed without manufacturing failures or changing application logic.

Coverage:

- Recommendation and no-ad keys one microsecond before, exactly at, and one microsecond after 24 hours. No-ad keys retain no-ad replay after inventory becomes eligible; mismatched user ownership remains 409 even at/after expiry. Durable recommendation identity/count cannot recycle.
- First impressions/clicks at the same strict creation-based boundaries. Previously accepted impressions/clicks replay exactly at/after expiry, with one credit in total for both $1.25 and zero bids.
- A transport wrapper raises on the first successful response send after commit. Retry retains the saved recommendation, original bid/title and attribution after bid, eligibility and profile edits. Selection creates no impression; click-before-impression returns 409, display confirmation permits retry, and future selection sees inactive inventory.
- Four simultaneous HTTP requests with one key (ad/no-ad), competing users sharing one key, and duplicate impressions/clicks. Tests hold a user-row or event-table lock and observe all four backend transactions blocked in PostgreSQL before releasing the gate, then assert durable single outcomes/events/revenue. Gate wait is bounded to two seconds; futures and database waits are bounded. Integration tests run serially.
- Real immediate insert and deferred commit failures for recommendation, no-ad, impression and click writes. Failure returns safe 503, rolls back recommendation/key or event/revenue, and retry after removing the trigger succeeds and replays without double credit. Unique trigger predicates target only fixture opportunities; triggers/functions are removed in `finally`.

Runtime: Windows CPython 3.10.11, pytest 9.1.1, existing PostgreSQL 18.6 and locked packages. Reused portable local PostgreSQL on 127.0.0.1:15432; created only `adflow_ticket08_test`, migrated explicitly. Configured application target `adflow_ticket03_dev` was never modified. Consulted official FastAPI dependency-override and PostgreSQL locking documentation, linked in README. No dependency versions changed. Windows TestClient/PostgreSQL execution used reviewed outside-sandbox commands; no unresolved auto-review rejection occurred.

Executed from repository root:

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -l '.local-postgres/server.log' -o '-h 127.0.0.1 -p 15432' start
& '.local-postgres/pgsql/bin/createdb.exe' -h 127.0.0.1 -p 15432 -U adflow adflow_ticket08_test
```

The database was prepared before confirmation; the server was stopped while waiting and restarted for the confirmed tests. Executed from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket08_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m alembic -x database=test upgrade head
.\.venv\Scripts\python.exe -m pytest tests/integration/test_http_resilience.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/integration/test_http_resilience.py -k first_event -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/integration/test_http_resilience.py -k lost_response -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/test_http.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Results after implementation: resilience file **28 passed in 6.21 seconds**; existing HTTP adapter file **30 passed in 3.94 seconds**. Full regression **186 passed in 22.67 seconds** (74 unit, 112 PostgreSQL integration). Strict mypy passed for 44 files; Ruff lint/format passed for 44 files; Alembic reported **No new upgrade operations detected**. An overlong test SQL string was split before final lint checks. Repository-root `git diff --check` passed.

This ticket verifies lifecycle correctness; it adds no throughput/latency claim and does not complete Docker packaging or the Phase 1 gate (tickets 09/10), or the human learning checkpoint.

### Review and commit — 2026-10-07

Committed the confirmed ticket 07/08 scope as `e04c518` on the current `main` branch. Used the code-review skill with independent parallel Standards and Spec agents over `git diff b95748da55befabf791a9302c29dea287116a2a2...HEAD`. Standards: zero documented violations or actionable baseline smells. The required thin routes and requested clock seam follow the architecture, and explicit scenario setup was judged readable. Spec: zero missing/partial requirements, scope creep or incorrect behavior; the reviewer checked the exact-clock, response-loss, lock-gated races, failure-trigger rollback and test-isolation evidence. Both reviews were read-only and inspected existing check results rather than rerunning them. No implementation fixes were needed.

Stopped PostgreSQL successfully after verification/review with repository-root `& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -m fast stop`. Ignored local runtime/data are retained for later tickets. Review and shutdown evidence is recorded in a follow-up documentation commit; implementation remains unchanged from the reviewed snapshot.
