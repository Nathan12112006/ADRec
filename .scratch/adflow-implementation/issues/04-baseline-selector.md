# 04 — Implement deterministic interest-overlap selection

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02

## Scope

Add baseline selection outside routes over active ads from active advertisers. Order by distinct shared-interest count descending, bid descending and ad ID ascending; preserve zero-bid eligibility. Keep selection separable from persistence for later retrieval integration.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Focused tests cover interest overlap, deterministic ties, empty interests, zero bids and inactive inventory.
- [x] Empty eligible inventory returns a no-ad result rather than a fabricated winner.
- [x] Explain scan time/space costs; no model invocation or invented predicted CTR.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented in `e16bdeb`, relative to pre-ticket commit `3d0f2df60abe95d0eb014c92be53a6580a40d7ed`.

Parallel code-review completed against `git diff 3d0f2df60abe95d0eb014c92be53a6580a40d7ed...HEAD` at `e16bdeb`. Standards: zero actionable findings; the reviewer requested recording pending ticket evidence before marking done, now supplied below. Spec: zero findings; all ticket 04 requirements satisfied. No review-driven code changes were needed.

Added `backend/app/ranking/baseline.py` and public package exports: immutable `BaselineCandidate` and pure `select_baseline`. Added `backend/app/db/selection.py`: `select_baseline_ad` joins active ads to active advertisers, streams ID/interests/decimal bid in 1,000-row batches, closes the result cursor, and returns a detached candidate or `None`. No routes, models, migrations or dependencies changed. Caller owns transactions and subsequent eligibility/bid revalidation; recommendation persistence belongs to ticket 05.

Selection uses distinct shared target interests descending, exact decimal bid descending, ad ID ascending. Empty interests/no overlap use bid/ID; zero bids remain eligible. Invalid eligible negative/nonfinite bids raise `ValueError`, following the governing ranking contract. No model call, CTR field or invented prediction exists. README documents both entry points, focused commands, and costs: expected O(U + N*A) selection work and O(U + A) selector space, plus O(B*A) adapter buffering with B=1,000. Database scans/joins and transmission remain baseline costs; no benchmark/latency claim is made. SQLAlchemy 2.0.54 streaming behavior was checked against its official ORM `yield_per` documentation linked in README.

Nathan confirmed both the pure selector and database selection seams. Red/green evidence: first pure-selector test failed to import the absent ranking package, then passed after implementation; inactive inventory test failed before eligibility filtering; invalid-bid tests failed before validation; database test failed to import the absent adapter, then passed against PostgreSQL after implementation. Remaining boundary/tie cases exercise these same public seams.

Added 14 unit cases and four PostgreSQL cases in `backend/tests/unit/test_baseline.py` and `backend/tests/integration/test_baseline_selection.py`. Unit tests cover repeated user/ad interests, overlap priority over bid, deterministic ties under reversed iterables, decimal precision, empty/no-overlap interests, zero bids, inactive ads/advertisers, empty eligible inventory and invalid bids. Database tests cover active joins, duplicate-interest counting, zero-bid selection, empty interests, ID ties and no-ad. Fixtures temporarily hide existing ads and insert edge inventory within rollback-only transactions, never committing inventory changes or deleting history. Tests run serially against the dedicated test database.

Runtime: Windows CPython 3.10.11, pytest 9.1.1, PostgreSQL 18.6, locked SQLAlchemy 2.0.54 and psycopg 3.3.6. Started the existing ignored portable server on localhost:15432 and created only the newly named isolated database `adflow_ticket04_test`; its migrations were applied by the integration fixture. Existing application database `adflow_ticket03_dev` was configured but not modified. Server stopped after verification; ignored cluster/database files retained.

Commands from repository root:

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -l '.local-postgres/server.log' -o '-h 127.0.0.1 -p 15432' start
& '.local-postgres/pgsql/bin/createdb.exe' -h 127.0.0.1 -p 15432 -U adflow adflow_ticket04_test
```

Checks from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket04_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_baseline.py -q
.\.venv\Scripts\python.exe -m pytest tests/integration/test_baseline_selection.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --tb=short
```

Results: focused unit suite **14 passed**; initial focused database test **1 passed**, expanded database cases all passed in the full suite. Full suite **81 passed in 13.05 seconds** (44 unit, 37 PostgreSQL integration). Strict mypy succeeded for 30 source files; Ruff lint and formatting checks passed (30 files). `git diff --check` passed. Sandbox denied initial database connections, and its initial server process did not remain available; reviewed outside-sandbox server/database/test execution succeeded. Git index writes also required reviewed execution. No automatic approval rejection remained unresolved.

Cleanup from repository root:

```powershell
& '.local-postgres/pgsql/bin/pg_ctl.exe' -D '.local-postgres/data' -m fast stop
```
