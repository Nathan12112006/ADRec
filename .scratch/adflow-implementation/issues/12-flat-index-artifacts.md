# 12 — Build and reload exact FAISS index snapshots

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 03, 10, 11

## Scope

Implement CPU IndexFlatIP build/load commands with stable ID mapping and manifest/checksums. Record catalog/vector/runtime/settings versions; validate complete artifacts and swap immutable references off the request path. Pin/smoke-test compatible CPU FAISS/NumPy in the actual runtime.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [11 — Define versioned topic vectors and the retrieval result contract](11-topic-vectors.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Normalized search, database-ID mapping and persisted reload agree on a known fixture.
- [x] Bad checksums/schema/mapping/runtime versions are rejected without replacing a working reference.
- [x] No live index mutation or per-request rebuilding; artifact preparation/reload commands are documented.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### 2026-10-07 — Implementation and verification

Implemented `backend/app/retrieval/snapshots.py`, `backend/app/db/catalog.py` and `backend/app/retrieval/cli.py`. Offline catalog export fingerprints one ordered PostgreSQL statement and includes only currently active ads/advertisers in the index. Snapshot preparation sorts positive database IDs, builds normalized float32 CPU IndexFlatIP vectors, stages and validates all three artifacts before publishing a new directory. The manifest records schema/builder/vector/vocabulary/catalog/runtime versions, dataset/snapshot identities, thread count, dimensions and SHA256 checksums. Loading verifies the complete manifest, runtime, mapping, native index and reconstructed vectors before `ActiveSnapshot` swaps a complete reference; readers holding an earlier reference retain it. Optional expected dataset/catalog checks reject stale or mismatched artifacts. There is no public live-mutation API or request-time build.

Added the `adflow-index` build/load CLI, an owned `/artifacts` directory and persistent Compose artifact volume. Updated README commands, compatibility/trust boundary, runtime pins, complexity and limitations. Locked FAISS CPU 1.15.1 with NumPy 2.2.6 below Python 3.14 / 2.3.5 on Python 3.14+, after checking official PyPI wheel availability. Python 3.14 is not exercised. Catalog export and validation are linear in catalog/vector count, sorting is O(n log n), exact search is O(n*d); no performance target or 100k-ad measurement is claimed.

Nathan approved the test seams: public snapshot build/load/search, active-snapshot reload, offline CLI with real FAISS and temporary artifacts, and isolated PostgreSQL catalog export. TDD reds preceded implementation for missing snapshot module, incompatible manifests/runtime, invalid mappings/native vectors, missing required fields, expected catalog/dataset checks, failed publication and missing artifacts. Added 41 snapshot cases, three CLI cases and ten PostgreSQL integration cases, including known IDs/cosines, corruption, retained active references, concurrent readers, eligibility/version changes and subprocess build/reload.

Checks from `backend/` (Windows CPython 3.10.11, native tests outside sandbox):

```powershell
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest --tb=short
```

Strict typing passed for 57 files; Ruff lint and formatting passed for 57 files. Final full suite: **314 passed in 45.39s** (192 unit, 122 PostgreSQL integration). Focused snapshot/CLI checks: 44 passed in 9.69s. Application and test Alembic checks both reported no new upgrade operations. `uv lock` / `uv sync --locked` succeeded; installed console entry point was exercised.

Docker commands from the repository root, isolated project `adflow-ticket12`:

```powershell
docker compose -p adflow-ticket12 config --quiet
docker compose -p adflow-ticket12 up -d --wait postgres
docker compose -p adflow-ticket12 exec -T postgres createdb -U adflow adflow_test
docker compose -p adflow-ticket12 build backend
docker compose -p adflow-ticket12 run --rm backend python -m alembic upgrade head
docker compose -p adflow-ticket12 run --rm backend python -m app.seeding.cli
docker compose -p adflow-ticket12 up -d --wait
docker build --check backend
docker compose -p adflow-ticket12 run --rm backend python -m app.retrieval.cli build --dataset-id 07415efc-7c8f-5781-92d1-e922d81fa502 --output /artifacts/ticket12-default
docker compose -p adflow-ticket12 run --rm backend python -m app.retrieval.cli load /artifacts/ticket12-default --interests technology gaming --limit 3
docker compose -p adflow-ticket12 down
docker compose -p adflow-ticket12 up -d --wait
docker compose -p adflow-ticket12 run --rm backend python -m app.retrieval.cli load /artifacts/ticket12-default --interests technology gaming --limit 3
docker compose -p adflow-ticket12 exec -T postgres psql -U adflow -d adflow -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events);"
docker compose -p adflow-ticket12 down
```

All passed; final counts `100|20|1000|0|0` confirm demo data unchanged after tests. An initial count query used a nonexistent table name, then was corrected to the schema above. Containers stopped; both `adflow-ticket12_postgres_data` and `adflow-ticket12_index_artifacts` volumes retained. Readiness returned 200/ready before shutdown. Image `adflow-backend:phase1` identity: `sha256:f562fa05e8c1bf4db54df5aa3686f3b7216d9d72609b600502af83a887478e0a`; Linux x86_64 CPython 3.12.15, PostgreSQL 18.6, FAISS 1.15.1, NumPy 2.2.6, one build/search thread. Docker build checks had no warnings.

Persisted Docker snapshot `4ce9768d-fe21-4ce0-80f5-61c4d42302c0` contains 1,000 ads and survived container recreation. Catalog identity `catalog-v1:c7f3d02a738e5839ed92316cb3731edb83b4dc940b8f48d55ec51bfac4f98257`; index SHA256 `5df9750aab97a4d3d75fa44b8de2e7ec215f9644cd613e57bd6ad6347da0a92b`; mapping SHA256 `93c93fc5d5d70ce15b4f36dbc813a073d792c38ee0e4567b2f0bf476945d72b9`. Query returned IDs `207398605419706012`, `219893576687798448`, `292840908465001150`, each score `0.9999999403953552`. A Linux three-entry temporary fixture independently passed known IDs `42,9001,700`, scores `1,~0.70710678,0`, and persisted reload.

The native installed `backend/.venv/Scripts/adflow-index.exe` also built and loaded `.uv-cache/ticket12-native` using the same dataset and query. Snapshot `aaa02e52-c1c2-45b8-82fb-f7e490b13b0f` produced identical index/mapping/catalog hashes and query IDs, with Windows AMD64 CPython 3.10.11 runtime metadata. Cross-runtime loading is deliberately rejected, requiring a rebuild in the target runtime; matching payloads do not imply general cross-platform compatibility.

Two sandboxed native pytest collections failed during FAISS DLL initialization. Minimal imports inside/outside the sandbox, five fresh native serialization probes, three repeated focused runs outside the sandbox and the final full suite passed. Diagnosis did not establish the cause; no product workaround or unproven compatibility claim was added. Artifacts are trusted local inputs: checksums detect accidental corruption, not malicious replacement; native FAISS deserialization is not an untrusted-file security boundary.

Ticket 13 now owns current request-time eligibility/backfill and fallback; ticket 15 owns serving integration. Phase 2 gate 17 and the separate human checkpoints remain open.
