# 13 — Implement current eligibility filtering and exact fallback

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 10, 11, 12

## Scope

Batch-load current ad/advertiser metadata, filter distinct eligible results, and expand queries to a configured bound before exact-current-inventory fallback. Mark stale catalog snapshots; handle missing/corrupt/incompatible indexes visibly. Provide empty-interest bid/ID fallback and no-ad/error separation.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [11 — Define versioned topic vectors and the retrieval result contract](11-topic-vectors.md)
- [12 — Build and reload exact FAISS index snapshots](12-flat-index-artifacts.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests cover ad/advertiser deactivation, missing IDs, new catalog data, limited inventory and candidate caps.
- [x] Missing/stale artifacts and insufficient filtered results use marked exact fallback; DB failure stays 503.
- [x] Selection-time eligibility remains enforced; fallback cost is not reported as nominal ANN performance.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### 2026-10-07 — Implementation and verification

Implemented `backend/app/retrieval/current.py`: `CurrentCandidateRetriever.retrieve` validates bounded limits, obtains a paired snapshot/status, checks the dataset's current revision, queries FAISS and batch-fetches current metadata, excludes missing/inactive/wrong-dataset ads, expands geometrically to the configured bound, and checks the revision again. Missing/corrupt/incompatible/stale snapshots or insufficient eligible hits use visibly marked exact current-inventory fallback. That fallback streams one PostgreSQL statement snapshot, scores all eligible vectors, retains a bounded heap, and returns at most the requested 500-candidate cap. Empty interests use bid-descending/ID-ascending eligible inventory with null similarity. Empty inventory is a successful empty result; PostgreSQL errors or invalid current data produce safe `WorkflowError(503, retrieval_unavailable)`.

Added migration `0003_catalog_revisions.py` and `CatalogRevision` in `models/records.py`. A separate revision table preserves immutable dataset provenance. Existing datasets are backfilled; new datasets initialize their own row. PostgreSQL row triggers advance revisions transactionally for ad/advertiser inserts, edits and deletes, including direct/bulk SQL. No-op updates are skipped; truncation conservatively invalidates all revisions. `db/catalog.py` now exports under a shared revision-row lock and records `catalog-v2:<dataset>:<revision>`, replacing the offline content hash. Older `catalog-v1` snapshots are marked stale and must be rebuilt. A normal indexed request performs primary-key revision reads rather than full-catalog fingerprint scans. Revisions serialize writes per dataset; offline export blocks catalog commits until the caller ends the transaction. These contention costs remain unmeasured.

`snapshots.py` now exposes typed `SnapshotLoadError` reasons and atomic `ActiveSnapshot.status()`. A failed explicit reload retains the old acquired reference while reporting a degraded state to new retrieval calls; successful reload clears it. No file loading, mutation or building occurs inside retrieval. `RetrievalResult` adds vector, metadata/orchestration and fallback timing plus returned-hit/expansion/fallback-scored counters. `elapsed_ms` includes every stage; fallback query/scoring is reported separately, never as nominal index latency. Updated README setup, migration/rebuild guidance, public adapter example, diagnostics and complexity.

Nathan explicitly approved the public `CandidateRetriever.retrieve` seam with real FAISS and isolated PostgreSQL, plus snapshot reload/failure diagnostics; existing lifecycle tests are the selection-time/503 regressions. Applied the implement and TDD skills. Observed red→green slices for the missing retriever module, missing-index cosine fallback, indexed/stale behavior, reload diagnostic reasons, expansion/timing counters and the large PostgreSQL ID-batch boundary. Additional regression cases exercise activation/deactivation, insert/delete/topic/bid/title changes, limited/empty inventory, 500-candidate caps, invalid limits/data, wrong datasets, cross-session freshness, rollback and reload recovery. No internal collaborators are mocked.

The 65,536-ID expansion fixture initially failed with the expanded per-ID SQL bind list. Typed PostgreSQL `ANY(bigint[])` now uses one bound array and passes; this protects the already-supported configured expansion range, not a performance claim. Reference: [SQLAlchemy ANY](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.any_). The fixture has 65,535 deliberately missing index IDs plus three real catalog ads; it does not demonstrate a 100k-ad workload.

Checks from `backend/` (Windows AMD64 CPython 3.10.11, pytest 9.1.1; native tests outside the sandbox):

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_candidate_retrieval.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/integration/test_candidate_retrieval.py tests/integration/test_recommendations.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

New retrieval file: **31 passed in 7.03s**. Earlier retrieval/selection focused run: **50 passed in 8.40s** before the final large-expansion case. Full final regression: **345 passed in 50.41s** (192 unit, 153 PostgreSQL integration). Strict mypy, Ruff lint and Ruff formatting passed for all 60 source files, including migrations. Both Alembic drift checks reported no new upgrade operations. Earlier lint/type issues were corrected before these final checks.

Verified an upgrade of existing data, rather than only fresh schema creation: on the new isolated application database, ran `python -m alembic upgrade 0002`, `python -m app.seeding.cli`, `python -m alembic upgrade head`, then `python -m alembic check` with the backend venv and URLs above. Default seed created 100 users, 20 advertisers and 1,000 ads before revision tracking existed. Migration backfilled revision zero without altering those rows or provenance. Dataset: `d059631d-9bf7-52dd-be45-bc75f781c7c1` (native CPython 3.10.11 seed manifest).

Docker commands from root:

```powershell
docker ps --format "{{.Names}} {{.Ports}}"
docker volume ls --filter name=adflow-ticket13
docker compose -p adflow-ticket13 up -d --wait postgres
docker compose -p adflow-ticket13 exec -T postgres createdb -U adflow adflow_test
docker compose -p adflow-ticket13 config --quiet
docker compose -p adflow-ticket13 build backend
docker build --check backend
docker compose -p adflow-ticket13 run --rm backend python -m alembic upgrade head
docker compose -p adflow-ticket13 run --rm backend python -m app.retrieval.cli build --dataset-id d059631d-9bf7-52dd-be45-bc75f781c7c1 --output /artifacts/ticket13-exact
docker compose -p adflow-ticket13 up -d --wait
Get-Content -Raw .uv-cache/ticket13-smoke.py | docker compose -p adflow-ticket13 exec -T backend python -
Invoke-RestMethod http://127.0.0.1:8000/health/ready
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
docker compose -p adflow-ticket13 exec -T postgres psql -U adflow -d adflow -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events), (SELECT revision FROM catalog_revisions WHERE dataset_id='d059631d-9bf7-52dd-be45-bc75f781c7c1');"
docker compose -p adflow-ticket13 down
```

Initial inventory showed no running containers or ticket-13 volumes. Docker build/config and build checks passed with no warnings. Linux x86_64 CPython 3.12.15, PostgreSQL 18.6, FAISS CPU 1.15.1, NumPy 2.2.6; smoke uses one native thread. Image identity `sha256:65677d3face417c7a4ab6ec3bbe6c9090fd99a1ecac084a8678361f62dcaebcf`. Readiness returned `{"status":"ready"}`; an initial check used the incorrect `/api/v1/health/ready` route, then was corrected. Post-suite counts were `100|20|1000|0|0|0`. Containers stopped; `adflow-ticket13_postgres_data` and `adflow-ticket13_index_artifacts` retained.

Docker snapshot `13bc9c89-61f7-43e8-a943-d6c2b7aba08b`, catalog `catalog-v2:d059631d-9bf7-52dd-be45-bc75f781c7c1:0`, 1,000 vectors; index SHA256 `be862485d7b35314c09947dab4ca52a83000920a97117e946ab76de71ea5db74`, mapping SHA256 `29ce538acdfc29834eeedc245b6dac6413b68052d665e447ca38a877475cab1d`. Query technology+gaming, limit 3 returned IDs `41055658037361572`, `120759592852820394`, `134653927587020761`, each cosine `0.9999999403953552`. A rollback-only ad deactivation produced stale fallback scanning 999 eligible vectors and excluded that ad; rollback restored index validity. A missing explicit reload produced marked fallback scanning 1,000 vectors, and successful reload recovered indexed mode. Empty interests returned bid/ID order with null scores. Rollback-only advertiser deactivation returned zero candidates. The smoke source remains locally at ignored `.uv-cache/ticket13-smoke.py`; persisted index artifacts are retained in the named volume.

Native installed CLI also built `.uv-cache/ticket13-native` with the same dataset (`backend/.venv/Scripts/adflow-index.exe build --dataset-id d059631d-9bf7-52dd-be45-bc75f781c7c1 --output .uv-cache/ticket13-native`). Ran the same smoke using `$env:ADFLOW_SMOKE_INDEX='.uv-cache/ticket13-native'; backend/.venv/Scripts/python.exe .uv-cache/ticket13-smoke.py`. Snapshot `7514210e-65be-4c81-8e34-205ed5e28d82` had identical catalog/index/mapping identities and candidate IDs; Windows AMD64 CPython 3.10.11 runtime metadata. Both native and Linux scenarios passed. Smoke timings are not warmed benchmarks or comparative performance evidence.

Selection-time locking/revalidation remains in the existing recommendation workflow and its real race tests passed. Ticket 15 owns integration/persistence of retrieval context; no serving default changed here. Ticket 14 is next eligible. Phase 2 gate 17, HNSW promotion, 100k-ad measurement and human checkpoints remain incomplete.

### 2026-10-07 — Final review

Implementation commit `05d0869` reviewed using `git diff 6b50a225a59d4af86daffd7ed03476da341e591c...HEAD` by independent parallel Standards and Spec reviewers under the code-review skill. Standards: **0 findings**; domain vocabulary, evidence rules, cohesive responsibilities, explicit costs and atomic diagnostics were respected. Spec: **0 findings**; current eligibility, bounded expansion, fallback reasons/timing, revision freshness and remaining ticket 14/15 boundaries satisfy the governing contract. Reviews were read-only; no checks rerun. Final `git diff --check` passed. Committed on the current `main` branch; isolated containers stopped and both volumes retained.
