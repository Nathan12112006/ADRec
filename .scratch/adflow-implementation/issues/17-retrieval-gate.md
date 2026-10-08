# 17 — Verify and record the candidate-retrieval phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 10, 16

## Scope

Execute retrieval/vector/ID/reload/filter/fallback checks and save comparison evidence, preparation commands and an explanation of exact scans versus bounded downstream ranking. Keep exact if ANN fails its gate.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [16 — Measure exact and approximate retrieval quality and cost](16-retrieval-benchmarks.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Canonical Phase 2 checks pass and evidence records actual dataset sizes and modes.
- [x] README/setup explains rebuild/fallback and measured tradeoffs.
- [x] Offer the retrieval learning checkpoint and unlock Phase 3 only after this technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Technical gate — 2026-10-08

Implemented using the implement skill. Review baseline: `7e376aadb3a0ed9d4e431409233b45b2a05dcf85`. Tickets 10 and 16 were done and the working tree was clean. No application behavior, dependencies or schema changed. Existing Nathan-approved public vector/snapshot/CLI and HTTP/PostgreSQL seams were sufficient; no new TDD seam was introduced. Added repeatable evidence scripts and saved outputs under [ticket17 evidence](../evidence/ticket17/); updated README with phase status, complexity, rebuild/fallback guidance and the learning exercise.

Focused unit retrieval suite: **159 passed** outside the sandbox (the mixed invocation also reported 71 database configuration errors, corrected below). Focused PostgreSQL retrieval suite: **71 passed in 45.52s**. Full final regression: **423 passed in 101.88s**, no skips. Strict mypy: **68 files passed**. Ruff lint/format: **68 files passed**. Alembic: **no new upgrade operations detected**. Offline lock check: **48 packages resolved**, passed. Hatchling wheel/sdist build passed. Evidence scripts were Ruff checked/formatted. `git diff --check` passed.

Coverage includes vector semantics/normalization/invalid inputs; empty interests; limits and ties; stable IDs; immutable persistence/reload and concurrent readers; corrupt/missing/incompatible/stale snapshots; current ad/advertiser eligibility, expansion/backfill and exact fallback; changed winner metadata; bounded recommendation ranking/replay; database failure behavior; and benchmark query/quality/reporting contracts. Full regression includes the lifecycle transactions and event accounting from Phase 1.

Native Windows Python 3.10.11 and Docker Linux Python 3.12.15 smoke checks both passed with FAISS 1.15.1 and NumPy 2.2.6. Each built/reloaded Flat and HNSW snapshots, recovered IDs `[42, 9001, 700]` and cosine scores `[1, 0.7071067690849304, 0]`, rejected a corrupt replacement and preserved the active snapshot. Outputs: [native](../evidence/ticket17/native-smoke.json), [Docker](../evidence/ticket17/docker-smoke.json). Docker image rebuilt from locked inputs: `sha256:608042bc9f57a46b27ea9cdfe1a8292dd7feab32e519df745e25abf13fe59282`. Docker smoke used temporary files and no database/network calls; it is not a new end-to-end Docker API walkthrough. Native HTTP/PostgreSQL integration supplies serving verification; earlier Docker startup evidence remains tickets 10/14.

### Saved scale evidence and decision

Audited both ticket-16 compressed raw reports against their summary hashes, summary contents and query hashes, actual query/sample counts, candidate bounds/distinctness, nearest-rank personalized retrieval P95 and failed promotion decisions. [Audit output](../evidence/ticket17/report-audit.json) preserves the raw SHA-256 values. Actual native datasets: small 100 users/20 advertisers/1,000 eligible ads; full 1,000 users/200 advertisers/100,000 eligible ads. Both use limit 500, one FAISS thread, concurrency one, three repetitions, tolerance 1e-6, HNSW M=32/efConstruction=200/efSearch=128; 20/30 nonempty queries plus three separate empty-interest queries, respectively.

| Population | Flat retrieval P95 ms | HNSW path P95 ms, including fallback | HNSW min tie-aware recall | Personalized fallback |
| --- | ---: | ---: | ---: | ---: |
| Small | 88.558 | 217.470 | 0.986 | 90% |
| Full | 40.715 | 6631.704 | 0.0 | 10% |

Modes in raw personalized samples: Flat `exact`; HNSW `hnsw` and `exact_fallback`. Empty-interest samples remain separate `nonpersonalized` observations without cosine recall. **Retain Flat**: HNSW fails the lower full-retrieval P95 gate on both sizes and the minimum recall gate at full scale. Original [comparison evidence](../evidence/ticket16/results.md) contains full-ad ranking, vector/metadata/ranking breakdowns, winner differences, repeated timings, memory and build/reload/artifact sizes. This gate audits those saved measurements, not a fresh benchmark, HTTP throughput or a universal speed claim. Full-ad and fallback scans remain visible. Flat bounds downstream ranking, not vector scanning: O(N*D) exact similarity work; C <= configured limit for ranking. Full-scale exact candidates changed the full-ad overlap-ranking winner in 33/90 samples. Similarity recall does not establish ranking quality.

Benchmark database reconciliation still returned **1,100 users, 220 advertisers, 101,000 ads, 0 recommendations, 0 events**. Data/history and original artifacts were preserved. Rebuild commands and full preparation identity remain in ticket 16 and README. Runtime/vocabulary/catalog changes require a new validated snapshot and explicit restart/reload; missing/stale/unusable snapshots visibly use exact current-inventory fallback. No request-time rebuild or HNSW promotion was introduced.

### Exact verification commands

From repository root, start the existing native server outside the Windows sandbox:

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket17-server.log -w
```

From `backend/`, outside the sandbox for atomic snapshot-directory renames and PostgreSQL access:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket16_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_topic_vectors.py tests/unit/test_retrieval_contract.py tests/unit/test_index_snapshots.py tests/unit/test_hnsw_snapshots.py tests/unit/test_index_cli.py tests/unit/test_retrieval_evaluation.py tests/unit/test_retrieval_benchmark_cli.py tests/integration/test_candidate_retrieval.py tests/integration/test_index_catalog.py tests/integration/test_retrieval_serving.py tests/integration/test_retrieval_benchmark.py --tb=short -q
.\.venv\Scripts\python.exe -m pytest tests/integration/test_candidate_retrieval.py tests/integration/test_index_catalog.py tests/integration/test_retrieval_serving.py tests/integration/test_retrieval_benchmark.py --tb=short -q
.\.venv\Scripts\python.exe -m alembic -x database=test check
.\.venv\Scripts\python.exe -m pytest --tb=short -q
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock --check --offline
.\.venv\Scripts\python.exe -m hatchling build
```

The first mixed focused run omitted the application URL: 159 unit tests passed, 71 database errors. The separate corrected integration invocation and full regression above passed. The initial sandbox run failed snapshot renames with WinError 5 and omitted the application URL; no application defect was inferred. A sandbox-started PostgreSQL process did not survive its command; restart outside the sandbox completed automatic recovery before successful tests. Early connection-timeout attempts were setup failures. No data reset was used.

From repository root (Docker access and native smoke outside sandbox):

```powershell
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket17/audit-reports.py > .scratch/adflow-implementation/evidence/ticket17/report-audit.json
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket17/runtime-smoke.py > .scratch/adflow-implementation/evidence/ticket17/native-smoke.json
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket17 --fix
backend/.venv/Scripts/python.exe -m ruff format .scratch/adflow-implementation/evidence/ticket17
docker compose config --quiet
docker compose build backend
Get-Content -Raw .scratch/adflow-implementation/evidence/ticket17/runtime-smoke.py | docker compose run --rm --no-deps -T backend python - > .scratch/adflow-implementation/evidence/ticket17/docker-smoke.json
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
.local-postgres/pgsql/bin/psql.exe -h 127.0.0.1 -U adflow -d adflow_ticket16_benchmark -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events)"
git diff --check
```

### Learning handoff

Ticket 17's technical gate passes and unblocks ticket 18/Phase 3. Offered [ticket 58](58-learning-retrieval.md): explain why faster vector search alone does not prove a better retrieval pipeline, then direct a small candidate-limit/search-depth change and verify candidate count, tie-aware quality and cost. Ticket 58 stays open; no human explanation, change or understanding is claimed complete.
