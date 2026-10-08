# 16 — Measure exact and approximate retrieval quality and cost

Status: ready-for-agent
State: active
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 03, 10, 14, 15

## Scope

Add reproducible component comparisons for full-ad ranking, Flat plus the same ranking and HNSW plus that ranking. Support full 100,000-ad entities, frozen query/eligibility snapshots, ties and separate fallback queries. Record provenance/build/memory/search/metadata/ranking costs.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [14 — Add the HNSW candidate-retrieval comparison](14-hnsw-option.md)
- [15 — Integrate candidate retrieval into recommendation serving](15-retrieval-serving.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Ordinary and canonical tie-aware recall, boundary tolerance and missed-superior counts are correct on fixtures; k=0 is unavailable.
- [ ] Actual scale/results are saved; only promote HNSW with lower full-retrieval P95 and at least 95% tie-aware recall.
- [ ] No ANN/full-scale/speedup claim is made for an unrun or smaller comparison.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation — 2026-10-08

Nathan confirmed public recall evaluation with known fixtures, plus the benchmark runner/CLI with real FAISS and isolated PostgreSQL, observing saved reports, frozen inputs, fallback separation and the promotion decision. Applied implement/TDD. Starting review point: `0e307cf4143977cce183667d9b334847c4cb27a9`. Source implementation committed as `29c0a0b` on current branch main.

Added app/retrieval/evaluation.py (ordinary/canonical tie-aware recall and conservative eligibility decision), benchmark.py (frozen component experiment and raw reports), benchmark_cli.py (explicit CLI), package entry point, unit and isolated PostgreSQL integration coverage, and README setup/measurement boundaries. No serving default, model, schema, ranking rule, dependency version, recommendation/event write or production HTTP flag changed.

Reference quality uses all frozen eligible exact topic-vector scores and Flat reference IDs, with absolute tolerance declared before measurement. G contains scores strictly greater than kth+tolerance; T contains scores within tolerance. The canonical capped boundary-credit formula preserves missed-superior counts. k=0 is unavailable. Duplicate/ineligible/oversized populations and invalid/incomplete exact references are rejected.

The runner freezes profiles and eligible ad metadata in one repeatable-read transaction and retains the existing shared catalog revision lock. Its offline session disables only local idle-in-transaction timeout so artifact preparation can finish; serving timeouts remain untouched. Exports actual metadata/eligibility and sampled queries, then builds and reloads complete Flat/HNSW snapshots. It restores prior FAISS threads. Warmup and reference quality preparation precede timing. Paths are deterministically interleaved for each query; empty-interest clones have separate population summaries. All paths use the same overlap/bid/ID ranking. No speedup or winner improvement is required or presumed.

Reports save input/source hashes, git revision, actual dataset/counts, runtime/hardware/database location, index manifests/settings, build/reload/file sizes, process memory/CPU observations, raw per-query candidate IDs and mode/timing/quality/winner/score/bid results, nearest-rank pooled percentiles and separate repetition summaries. Full-ad measurement materializes required ID/interests/bid metadata to separate metadata and ranking costs (O(N) harness memory). Process RSS/peak includes catalog, references and all indexes; serialized bytes are separate, not mislabeled incremental native memory. Component totals exclude HTTP, profile lookup, durable writes and events. Same-process component repetitions do not claim Phase 8 steady-state load-test evidence.

Promotion eligibility is deliberately conservative: three repetitions, strictly lower full-retrieval P95, every query tie-aware recall >=95%, and no personalized fallback. The runner never applies a setting change. Existing output directories are refused; errors/interruption retain failed status without claiming complete output. Final report is written after the read transaction ends.

TDD evidence: absent evaluation module import failed before first tie/missed-superior implementation; empty catalog raised IndexError before unavailable k=0 behavior; invalid returned populations failed to raise before validation; absent runner import failed before implementation; absent promotion function import failed before threshold evaluation; CLI module help failed before CLI implementation. Initial runner integration exposed a variable rename error, corrected before passing. Focused final tests: 24 passed in 20.21 seconds, including actual CLI save/refusal, empty inventory, failed status, and a lock-gated concurrent profile editor proving frozen query interests. Strict mypy: 68 files passed. Ruff lint/format: 68 files passed. Wheel/sdist built with Hatchling; wheel console entry points inspected and include adflow-retrieval-benchmark. A bare uv command was unavailable on PATH; repository-local uv was located for lock validation. No new packages were introduced.

Prepared separate adflow_ticket16_test and adflow_ticket16_benchmark databases, preserving all existing data. Actual benchmark seed 160016 completed with 1,000 synthetic users, 200 advertisers and 100,000 ads, dataset caef4b11-279d-57b3-a015-01e0027f1370. Preparation is outside timed measurements. Benchmark results, final regression and reviews are recorded below when complete; this paragraph alone makes no performance claim.

### Saved measurements and exact commands — 2026-10-08

Actual native component results are retained in [results.md](../evidence/ticket16/results.md), readable summary JSON, compressed full raw reports (including candidate IDs/timing/quality/winner samples) and selected query JSON under ../evidence/ticket16/. Complete catalog exports and index artifacts remain in ignored local artifacts/retrieval-ticket16-small/ and artifacts/retrieval-ticket16-full/. The committed reports retain their manifests/checksums. Neither serving default nor runtime configuration was changed.

Small run: 1,000 ads, 100 users, 20 advertisers; seed 160017; dataset 339aa2ad-bd42-582c-9df9-2bd21d1f97d6; run 0c571188-ebeb-46f8-bdd8-12439799b10d. 20 nonempty queries × 3 repetitions, 3 empty-interest queries × 3 repetitions; candidate limit 500, warmup 5 per path, query seed 1601, tolerance 1e-6, one thread/caller. Flat full-retrieval P95 88.558ms; HNSW path including fallback 217.470ms. HNSW minimum tie-aware recall 98.6%, mean 99.93%; personalized fallback rate 90%. Gate failed.

100,000-ad run: actually 1,000 users and 200 advertisers; seed 160016; dataset caef4b11-279d-57b3-a015-01e0027f1370; run 80773bde-0043-4e3b-8228-93b0552b5345. 30 nonempty queries × 3 repetitions, 3 empty-interest queries × 3 repetitions; limit 500, warmup 10 per path, query seed 1601, tolerance 1e-6, one thread/caller. Flat full-retrieval P95 40.715ms; HNSW path including fallback 6631.704ms. 81/90 personalized HNSW-path samples were nominal HNSW and 9/90 were exact fallback due to insufficient candidates. HNSW mean tie-aware recall 86.667%, minimum 0%; four queries had zero recall across all repetitions. Zero missed-strictly-superior count does not imply perfect quality when the exact top-k lies in a tied maximum group. The table in results.md separately reports nominal HNSW and fallback samples. Gate failed on quality, latency and fallback. Retain Flat.

Both use HNSW M=32, efConstruction=200, efSearch=128; no tuning sweep or best-case cherry picking. Full Flat index bytes 5,200,045; HNSW 32,420,834, with process-wide memory observations separately labeled. Same-process short component repetitions do not certify Phase 8's independent steady-state HTTP comparisons. No positive percentage speedup, CTR/revenue lift, universal quality, API capacity or Docker-runtime benchmark claim. Native Python 3.10.11, FAISS 1.15.1, NumPy 2.2.6 and PostgreSQL 18.6 were actually used; report provenance includes processor/OS/CPU count and database co-location.

PowerShell from repository root, outside the sandbox for database access (existing data preserved):

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket16_test
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket16_benchmark
```

Focused checks from backend/:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket16_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_retrieval_evaluation.py tests/unit/test_retrieval_benchmark_cli.py tests/integration/test_retrieval_benchmark.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m hatchling build
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock --check --offline
```

Lock validation resolved 48 packages and passed. Package scripts were verified in built wheel entry_points.txt. No dependency lock changes were needed.

Actual seed/comparison invocations from backend/, outside the sandbox, sequentially (no regression suite running during measurement):

```powershell
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket16_benchmark'
.\.venv\Scripts\python.exe -m alembic -x database=test upgrade head
.\.venv\Scripts\python.exe -m app.seeding.cli --database test --seed 160016 --users 1000 --advertisers 200 --ads 100000 --append
.\.venv\Scripts\python.exe -m app.retrieval.benchmark_cli --database test --dataset-id caef4b11-279d-57b3-a015-01e0027f1370 --output ../artifacts/retrieval-ticket16-full --queries 30 --empty-queries 3 --warmup-queries 10 --repetitions 3 --limit 500 --threads 1 > ../.uv-cache/ticket16-full-console.json
.\.venv\Scripts\python.exe -m app.seeding.cli --database test --seed 160017 --users 100 --advertisers 20 --ads 1000 --append > ../.uv-cache/ticket16-small-seed.json
.\.venv\Scripts\python.exe -m app.retrieval.benchmark_cli --database test --dataset-id 339aa2ad-bd42-582c-9df9-2bd21d1f97d6 --output ../artifacts/retrieval-ticket16-small --queries 20 --empty-queries 3 --warmup-queries 5 --repetitions 3 --limit 500 --threads 1 > ../.uv-cache/ticket16-small-console.json
```

The full native component run started 19:14:23 UTC and finished 19:21:44 UTC. The longer full-ad/fallback scans are part of its actual component costs, not a timeout or incomplete scale attempt. All three paths and all declared repetitions completed. Preparation/build/reference work and harness processing make wall time different from summed measured component durations.

From repository root, a temporary standard-library rendering script at .uv-cache/write_ticket16_evidence.py copied the actual complete reports/queries into the ticket evidence directory and rendered results.md; it did not alter observations. Raw report SHA-256 is retained in each summary. Original full JSON reports/catalogs/indexes are retained locally. Regenerating timings requires a new output directory; they are measurements, not deterministic constants.

Final full checks from backend/ (separate test URL restored):

```powershell
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket16_test'
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m alembic -x database=test check
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```
