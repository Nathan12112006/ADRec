# 03 — Generate reproducible configurable entity seeds

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02

## Scope

Build an explicit seed CLI defaulting to 100 users, 20 advertisers and 1,000 ads with zero history. Support configurable counts including the full entity scale, seeded independent streams, vocabulary/category relationships, active inventory, nonnegative bids and dataset provenance. Define safe repeat invocation and dataset replacement behavior without automatic history overwrite.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Same seed/configuration reproduces entities and references; counts and relationships are checked.
- [x] Small seed works without FAISS, ML, Redis or experiment artifacts.
- [x] Existing lifecycle history is not silently cleared; commands and synthetic assumptions are documented.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented in `fe24932`, reviewed against pre-ticket commit `7b77e5746f6c2ec3841c39b45c1105f4210214f9`. Parallel Standards and Spec reviews found no implementation issues. Spec review requested full-run resource evidence; measurements below resolve that evidence item. All acceptance criteria passed.

Added `app/seeding/generation.py`, `persistence.py`, `cli.py` and the public package exports; added the `adflow-seed` console entry point, unit/CLI/PostgreSQL seed tests, and README commands, synthetic assumptions and complexity explanations. No dependency or schema changes were needed.

Behavior: defaults are 100 users, 20 advertisers, 1,000 ads, seed 42, zero lifecycle/history generation. Counts are configurable, including 10,000/100/100,000; ads require advertisers. Versioned uniform synthetic distributions use the brief's 13 topics, related category interests, age groups/countries/devices, all-active ordinary inventory and decimal $0.25–$5.00 bids. Empty-interest/zero-bid/inactive cases remain separate edge fixtures. Complete provenance records seed, counts, generator/Python versions, vocabulary/relationships, distributions, zero historical counts and null simulated time range/splits.

SHA-256-derived independent streams generate users, advertisers and ads. Complete-manifest UUIDs and deterministic positive 63-bit entity IDs preserve references independently of database sequence state and batch size. Reproducibility is scoped to the recorded generator/Python runtime; dataset loading timestamps are operational rather than simulated entity data. Hash ID conflicts fail and roll back rather than overwriting.

Persistence is one transaction with bounded bulk batches (default 1,000; allowed 1–10,000). Identical dataset inputs are a no-op, preserving inventory edits and lifecycle history. Different inputs refuse to write unless `--append` is explicitly supplied. Replacement means using a fresh database; no destructive reset/replacement flag exists. Append preserves history and expands available inventory. A bounded PostgreSQL transaction advisory lock serializes cooperating seeders. Tests prove concurrent identical seeders create one dataset and that an insertion conflict after an earlier batch rolls back the entire seed.

Nathan confirmed the public generator/seed CLI and persisted-count/reference/history seams. Recorded failing tests for the absent generation interface, persistence function and CLI before implementing those slices. Tests verify deterministic entities, independent streams, counts/relationships/payloads, manifest identity, input validation, history preservation through repeat/refusal/append, atomic rollback and concurrent invocation. No FAISS, ML, Redis or experiment artifacts are used.

Runtime: Windows, CPython 3.10.11, uv 0.12.23, SQLAlchemy 2.0.54, PostgreSQL 18.6, psycopg 3.3.6. Reused the ignored portable PostgreSQL cluster from ticket 02 on localhost port 15432. Only newly named isolated databases were created; existing data was not cleared. Primary API references for bulk insertion, advisory locks and Python random reproducibility are linked in README.

Executed verification from `backend/` (bootstrap uv is `../.venv/Scripts/uv.exe`):

```powershell
$env:ADFLOW_DATABASE_URL = 'postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_dev'
$env:ADFLOW_TEST_DATABASE_URL = 'postgresql+psycopg://adflow@127.0.0.1:15432/adflow_ticket03_test'
$env:ADFLOW_RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Full suite: **63 passed in 11.76 seconds** (30 unit, 33 PostgreSQL integration). Alembic reported **No new upgrade operations detected**. Focused generator/CLI tests passed (8 tests) and seed persistence checks passed during implementation; final suite also includes concurrent seeding.

Other passing checks:

- `.venv/Scripts/python.exe -m mypy` — success, 25 source files.
- `.venv/Scripts/python.exe -m ruff check .` — all checks passed.
- `.venv/Scripts/python.exe -m ruff format --check .` — 25 files formatted.
- `../.venv/Scripts/uv.exe sync --locked --offline --cache-dir ../.uv-cache` — passed, installed CLI available.
- `../.venv/Scripts/uv.exe build --no-build-isolation --offline --cache-dir ../.uv-cache` — source archive and wheel built.
- `git diff --check` — passed.

Actual CLI checks used fresh databases created with `createdb.exe -h 127.0.0.1 -p 15432 -U adflow <name>` and explicitly migrated using `.venv/Scripts/python.exe -m alembic upgrade head`:

- Application target `adflow_ticket03_cli`: `.venv/Scripts/adflow-seed.exe` created exactly the default 100/20/1,000 configuration, dataset `d059631d-9bf7-52dd-be45-bc75f781c7c1`. Identical invocation returned `already_exists` with the same manifest/identity. JSON outputs are retained under ignored `.local-postgres/ticket03-small.json` and `ticket03-repeat.json`.
- Application target `adflow_ticket03_full`: `.venv/Scripts/adflow-seed.exe --users 10000 --advertisers 100 --ads 100000` created dataset `2d408019-0767-5bd1-80bc-7fe6bc0fdf29` in **11.6157506 wall seconds**. Independent SQL assertions counted 10,000 users, 100 advertisers, 100,000 ads, zero recommendations/request outcomes/events, and 100,000 active ads joined to active advertisers with matching dataset references. Manifest output is ignored `.local-postgres/ticket03-full.json`.
- Resource profiling used another fresh application database, `adflow_ticket03_profile`, and the equivalent `python -m app.seeding.cli --users 10000 --advertisers 100 --ads 100000` (default batch 1,000). The base CPython 3.10.11 executable was launched directly with the locked virtual environment's `Lib/site-packages` on process-local `PYTHONPATH`, avoiding Windows console/venv launcher counters. It created the same full dataset identity in **11.5459007 wall seconds**. Polling the Python process every 50 ms observed maximum OS `PeakWorkingSet64` of **64,577,536 bytes (61.6 MiB)** and cumulative CPU time of **10.140625 seconds**. These are observed client-process counters; final polling intervals can be missed, and PostgreSQL server resource use is excluded. Output is ignored `.local-postgres/ticket03-profile.json`. An earlier launcher-only measurement was discarded as unrepresentative of generator resource use.

Generation work is O(users + advertisers + ads), with O(batch size) working memory plus fixed vocabulary/import overhead; database index maintenance adds storage/write cost. One atomic transaction avoids partial datasets but grows with the dataset. Recorded full-run time/resource values describe this host and run, not a universal throughput promise. Subsequent retrieval/model phases own large-scale serving and historical exposure/outcome generation. Database operations/TestClient/builds required reviewed execution outside the sandbox. The disposable PostgreSQL server is stopped after verification; ignored runtime/data are retained for later checks.
