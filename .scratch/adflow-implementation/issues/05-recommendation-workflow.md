# 05 — Persist recommendations and idempotent request outcomes

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02, 04

## Scope

Implement the recommendation service: required request-key association, replayable selection/no-ad outcomes, immutable bid/ad snapshot, 24-hour expiry and key/user conflicts. Atomically persist selection/outcome, revalidate eligibility and keep saved score/bid coherent. Recover concurrent uniqueness conflicts and response-loss retries.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)
- [04 — Implement deterministic interest-overlap selection](04-baseline-selector.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Same key/user replays the same selection or no-ad outcome; another user conflicts; expired keys do not create new opportunities.
- [x] Concurrent requests and commit-then-response-loss yield one durable outcome.
- [x] Unknown users and required database failures preserve 404/503 semantics; no unsaved success.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implementation commit `8e47cfd`, relative to pre-ticket commit `161d0978a279549c23277ecff7038c0d3ed92705`. Parallel code-review used `git diff 161d0978a279549c23277ecff7038c0d3ed92705...HEAD` at that implementation commit. Standards: zero actionable findings; requested completion evidence is recorded below. Spec: zero actionable findings, all ticket 05 requirements satisfied. No review-driven code changes were needed.

Added `backend/app/services/recommendations.py`, its package initializer and `backend/app/core/errors.py`. The public `recommend(session, user_id, request_key, clock=...)` workflow owns its transaction and returns a detached, immutable result only after commit. New selections persist a recommendation and globally unique request outcome atomically; no-ad persists only the outcome. `AdSelection` snapshots complete display fields, ID/advertiser, decimal bid, distinct overlap score, score meaning, baseline strategy/version and null predicted CTR. Recommendation bid and JSON bid (a decimal string) describe the same locked decision. No impression is recorded.

Replay uses saved ID, timestamp and JSON selection without inventory/profile reads or reranking. Same key/user replays for strictly less than 24 hours; exact boundary and later requests return 410 without key reuse. Key ownership is checked first and another user gets 409. Unknown users get 404. Keys are preserved exactly, must contain 1–255 characters and cannot be blank (422). `WorkflowError` carries safe message/code/status for ticket 07 to translate; HTTP routes and events remain tickets 07/06.

Extended `backend/app/db/selection.py` with optional dataset filtering. Existing composite recommendation foreign keys require user and ad to share a dataset, so serving scans the user's dataset rather than selecting incompatible ads from appended datasets. Original unrestricted selector callers remain supported. No schema, migration or dependency changes were needed.

For new decisions, the service share-locks the user profile and then the selected ad/advertiser, rechecks activity, bid and interests and builds the snapshot under those locks. Changed metadata rolls back and rescans, up to three attempts; sustained churn yields retryable 503. Row locks are held through commit. Other candidates can change during the scan: this guarantees coherent winner revalidation, not a serializable snapshot of all inventory. Only a `request_outcomes_pkey` unique violation triggers race recovery; the losing transaction (including any recommendation) is rolled back before reading the winner in a new transaction. Required read/write/commit/pool/lock failures produce safe 503, never an unsaved success. Replay receipt time is captured once across recovery. Production timestamps come from the server UTC clock; injectable clock is a service test seam, not a client payload.

Nathan instructed continuing ticket 05 after the proposed recommendation-service/PostgreSQL test seam confirmation. TDD slices recorded absent-service import failure, then successful creation; replay and no-ad failed before those branches existed; conflict/expiry/unknown-user tests failed before workflow error support; concurrent no-ad requests exposed a real PostgreSQL unique violation before recovery; unavailable-database and insert/commit failure tests raised raw database exceptions before safe 503 translation; three in-flight inventory edit cases returned early before locking/revalidation; blank/oversized keys failed before service validation. Each slice passed after its implementation. Typechecking and focused tests ran repeatedly.

Added 20 PostgreSQL service cases in `backend/tests/integration/test_recommendations.py`: complete snapshot/committed return, response-loss replay after bid/title/activity/profile changes, replayable no-ad and fresh-key selection, key/user conflict before expiry, one microsecond before/exactly at/after 24 hours for selected and no-ad outcomes, unknown user, eight simultaneous retries for selected/no-ad outcomes, simultaneous different users, unavailable database, actual immediate-insert and deferred-commit rejection with atomic rollback and successful retry, bid/ad/advertiser edits while selection is in flight, and invalid keys. Concurrency tests inspect durable counts to exclude orphan recommendations. In-flight edits use real row locks and `pg_blocking_pids`, not mocked internal selection calls. Failure triggers are limited to unique fixture users and removed in `finally` blocks. Fixtures append unique records; no reset or durable-history deletion occurs. Tests run serially.

README documents interfaces, statuses, key behavior, dataset scope, snapshot representation, concurrency/lock limits, tests and complexity. New requests retain expected O(U + N*A) scan work and bounded 1,000-row buffering; at most three scans on metadata changes. Replays perform indexed key/recommendation lookups and no inventory scan. History grows with opportunities, and row locks can delay editors; configured database waits are bounded, not the entire request. No performance improvement is claimed. SQLAlchemy 2.0.54 transaction handling and PostgreSQL 18 row locks were verified against official documentation linked in README.

Runtime: Windows CPython 3.10.11, pytest 9.1.1, PostgreSQL 18.6, SQLAlchemy 2.0.54 and psycopg 3.3.6 from the existing lock. Reused the ignored portable PostgreSQL cluster on localhost:15432 and created only the new isolated `adflow_ticket05_test` database, migrated by the fixture. `adflow_ticket03_dev` was the configured application target, never modified by these tests. Missing randomly named database connections intentionally exercise unavailability. Database/TestClient and Git-index operations required reviewed execution outside the sandbox; no unresolved approval rejection occurred.

Executed from repository root:

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -l '.local-postgres/server.log' -o '-h 127.0.0.1 -p 15432' start
& '.local-postgres/pgsql/bin/createdb.exe' -h 127.0.0.1 -p 15432 -U adflow adflow_ticket05_test
```

Executed from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket05_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_recommendations.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Results: focused service suite **20 passed in 1.43 seconds**. Final full suite **101 passed in 14.32 seconds** (44 unit, 57 PostgreSQL integration). Strict mypy succeeded for 34 source files; Ruff lint/format passed (34 files). Alembic: **No new upgrade operations detected**. Repository-root `git diff --check` passed. An intermediate Ruff import-order/loop-capture check failed and was fixed before final checks.

After verification, stopped the disposable server successfully from the repository root with `& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -m fast stop`. Ignored runtime/database files are retained for future checks. This technical ticket does not certify the later human learning checkpoint.
