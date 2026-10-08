# 02 — Implement PostgreSQL sessions and initial schema migrations

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 01

## Scope

Add SQLAlchemy session/transaction lifecycle and Alembic migrations for users, advertisers, ads, request outcomes, recommendations and events. Include decimal bids/revenue, UTC timestamps, dataset identity and immutable selection snapshots. Encode request-key uniqueness, event deduplication and referential integrity in PostgreSQL; retain durable history.

## Dependencies

- [01 — Create the backend package and configuration foundation](01-backend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] A fresh isolated database reaches the intended schema via migrations; no startup create_all shortcut.
- [x] Constraint tests prove duplicate keys/events and invalid relationships cannot bypass persistence rules.
- [x] Pool/connect/query waits are bounded and failures roll back safely.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented by Codex in `1d9d992`, reviewed against pre-ticket commit `4548eddd62861970f8d8d763592f6898c4f418fd`. Parallel Standards and Spec reviews both reported zero findings. All acceptance criteria passed.

Files/behavior:

- `app/db/session.py`: lazy bounded PostgreSQL engine; `session()` closes/rolls back unfinished work; `transaction()` commits on successful exit and rolls back body/flush/commit exceptions. FastAPI lifespan owns engine disposal; synchronous request dependencies supply sessions without committing during response teardown.
- `app/models/records.py`: typed Dataset, User, Advertiser, Ad, Recommendation, RequestOutcome and Event records. Dataset provenance includes UUID, seed, generator version and JSON configuration. Entity and recommendation foreign keys keep dataset references coherent.
- `migrations/versions/0001_initial.py`: explicit initial schema, globally unique request keys, one outcome per recommendation with matching user, event pair primary key, amount/type checks, foreign keys, lookup indexes, `NUMERIC(12,4)` money and timezone-aware timestamps. A null recommendation represents a no-ad outcome.
- `migrations/versions/0002_immutable_history.py`: database-level append-only protection for dataset provenance and recommendation/request/event history (updates, deletes and truncation rejected). No cleanup, cascading delete or startup `create_all` is used. Downgrades deliberately refuse history destruction.
- `alembic.ini`, migration environment/template: application/test target selection, offline SQL, explicit upgrades and metadata drift detection.
- Added statement/lock timeout settings in configuration and `.env.example`; pool/connect/statement/lock waits are bounded, connections use UTC, idle transactions disconnect after 30 seconds. Database exceptions hide SQL parameters.
- Updated dependency lock, README local database/migration/test commands and transaction ownership guidance, plus opt-in PostgreSQL integration tests. `.local-postgres/` is ignored disposable tooling, not committed application data.

Runtime/dependency identity: Windows, CPython 3.10.11, uv 0.12.23, SQLAlchemy 2.0.54, Alembic 1.20.0, psycopg/psycopg-binary 3.3.6, PostgreSQL 18.6. Version-sensitive APIs checked against primary SQLAlchemy transaction, Alembic tutorial, PostgreSQL timeout and psycopg install documentation linked in README.

PostgreSQL verification used official EDB portable binaries from `https://sbp.enterprisedb.com/getfile.jsp?fileid=1260609`, referenced by its download-binaries page. Download SHA256: `E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2`. Runtime extracted only bin/lib/share under ignored `.local-postgres/`. Initialized with `initdb.exe -D .local-postgres/data -U adflow -A trust -E UTF8 --locale=C`; started using `pg_ctl.exe -D .local-postgres/data -l .local-postgres/server.log -o '-h 127.0.0.1 -p 15432' -w start`. This disposable cluster listened only on localhost; it was not installed as a Windows service. Existing databases were not reset or cleared.

TDD seams were confirmed by Nathan. Recorded failing tests for the absent database module, missing user/request schema, and mutable selection snapshots before implementing those slices. Further tests cover raw invalid writes, cross-dataset/user relationships (asserting the actual foreign-key violation), no-ad representation, snapshot preservation after ad edits, immutable timestamps/history, decimal click revenue/event deduplication, rollback of preceding writes on commit failure, uncommitted session cleanup, and real stalled connection/pool/query/lock waits followed by recovery. Workflow ordering/expiration and captured-bid credit equality remain tickets 05/06.

Final verification from `backend/` used these process environment values:

```powershell
$env:ADFLOW_DATABASE_URL = 'postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket02_dev'
$env:ADFLOW_TEST_DATABASE_URL = 'postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket02_final_test'
$env:ADFLOW_RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
.\.venv\Scripts\python.exe -m alembic -x database=test current
```

Created `adflow_ticket02_final_test` fresh with `createdb.exe -h 127.0.0.1 -p 15432 -U adflow adflow_ticket02_final_test`. The integration fixture migrated it from empty to head before checks. Full result: **52 passed in 10.10 seconds** (30 PostgreSQL integration, 22 unit). Alembic reported **No new upgrade operations detected** and **0002 (head)**. The application URL intentionally named a different database and was not accessed during integration tests.

Other passing commands from `backend/`:

- `.venv/Scripts/python.exe -m pytest tests/integration/test_persistence.py --tb=short` — 26 passed.
- `.venv/Scripts/python.exe -m pytest tests/integration/test_persistence.py -k cross_dataset --tb=short` — 1 passed after tightening the foreign-key exception assertion.
- `.venv/Scripts/python.exe -m alembic -x database=test upgrade head` — repeated upgrade passed without changes; subsequent `check` still reported no drift.
- `.venv/Scripts/python.exe -m alembic upgrade head --sql` — offline SQL generated under ignored tooling directory.
- `.venv/Scripts/python.exe -m mypy` — success, 18 source files.
- `.venv/Scripts/python.exe -m ruff check .` — all checks passed.
- `.venv/Scripts/python.exe -m ruff format --check .` — 18 files formatted.
- `../.venv/Scripts/uv.exe sync --locked --offline --cache-dir ../.uv-cache` — passed.
- `../.venv/Scripts/uv.exe build --no-build-isolation --offline --cache-dir ../.uv-cache` — source archive and wheel built.
- `git diff --check` — passed.

Tradeoffs/limits: explicit immutable JSON ad snapshots avoid replay joins to changing inventory; composite references add indexes but keep relationship integrity in PostgreSQL. Durable history grows with opportunities/events; no performance claim is made. Server statement timeout bounds SQL execution rather than an overall HTTP/network deadline. Administrative owners can alter triggers/schema. Docker Desktop failed startup on its inference socket, so no Docker success is claimed; packaging verification remains ticket 09. Downloads, database/native processes and Windows TestClient checks required reviewed execution outside the sandbox. Only the stated Windows/Python/PostgreSQL runtime was exercised. Portable runtime/data are ignored and retained for possible later checks; the server is stopped after verification.
