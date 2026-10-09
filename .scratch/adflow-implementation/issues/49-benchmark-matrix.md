# 49 — Execute the controlled performance comparison matrix

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 16, 37, 45, 48

## Scope

Run matched full-scan/Flat/HNSW and cache-enabled/disabled comparisons with ranking/model/dataset held fixed. Exercise requested user counts and access/cache patterns within machine capacity.

## Dependencies

- [16 — Measure exact and approximate retrieval quality and cost](16-retrieval-benchmarks.md)
- [37 — Measure profile-cache behavior under reproducible access patterns](37-cache-comparison.md)
- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [48 — Produce honest latency and workload reports](48-benchmark-reporting.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Save raw artifacts and provenance for each attempted run; report incomplete or failed configurations without extrapolation.
- [x] No comparative performance result is quoted; the paired smoke reports have one short repetition and are labeled accordingly.
- [x] No 100k-ad or HNSW promotion is claimed; the actual 100k-ad evidence in ticket 16 shows the quality/latency gate failed.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Claimed by Codex on 2026-10-09 after dependencies 16, 37, 45 and 48 were done.

### Runner and matched smoke changes

- Added `backend/Dockerfile.locust` using the pinned Locust 2.46.7 image and locked app database libraries. `benchmark_runner.py` can run Locust in that image over the API container's network namespace, so the Python 3.10 host can still inspect Docker and PostgreSQL while the generator uses Python 3.13.
- Fixed relative output paths and explicit `None` handling in Docker command metadata. The short runner smoke produced complete JSON, phases, CSV, HTML, server snapshots and reports with a clean Locust CSV-writer shutdown.
- Changed cold-cache preparation to delete only the benchmark dataset's exact versioned profile keys through Redis. Added a validated `disabled` Redis setting so Compose can run a real cache-off service.
- Added `adflow_benchmark_template`, a migrated, fixed 1,000-user/1,000-ad synthetic baseline using seed 4901 and dataset `458a3900-0e21-57cc-88ca-877c7999f95d`. Extended `reset_benchmark_database.py` to clone only that exact template into `adflow_benchmark` after verifying the template exists. The application and test databases are rejected as reset targets. The PowerShell driver can reset the isolated benchmark database before each configuration.
- Added `backend/scripts/run_benchmark_matrix.ps1` and documented setup. It covers full-scan/Flat/HNSW, Redis on/off, recommendation-only/lifecycle, uniform/hot profiles, and warm/targeted cold cache.

### Evidence

- Paired 10-user smoke: 24 configurations, 24/24 complete runs and reports, all on the same dataset and ranking (`interest-overlap`) with no CTR model. Every run began with 1 dataset, 1,000 users, 1,000 ads, zero recommendations, zero request outcomes and zero events. There were no transport, timeout, HTTP, semantic or failed-opportunity counts. Settings were 1 second warm-up, 3 seconds measured, 3 seconds finite drain, one repetition. These checks verify matched configuration behavior and workload correctness; they are not latency or throughput comparisons.
- Paired output: `artifacts/benchmarks/ticket49-paired-10/`; each variant/access/workload folder has `matrix.json`, `run.json`, phases, counters, server snapshots, Locust CSV/HTML/logs, and `report.md`/`report.json`.
- Separate user-count smoke: `artifacts/benchmarks/ticket49-matrix-smokes-final/` retains 24 configurations and 72 attempts at 10/100/500 users. All 10-user attempts completed with zero request errors. At 100 and 500 users the one-worker API saturated, producing thousands of timeouts and failed opportunities; at 500, zero selections completed in the short measurement window and observer metrics sometimes timed out. These rapid-ramp diagnostics are not paired: their starting durable table counts differed across configurations, so they are not used to compare retrieval or cache behavior.
- Ticket 16's 100,000-ad run used dataset `caef4b11-279d-57b3-a015-01e0027f1370`; Flat full-retrieval P95 was 40.715 ms, while the HNSW path including fallback was 6,631.704 ms. HNSW mean tie-aware recall was 86.667%, minimum 0%, and the promotion gate failed. Flat remains the serving default. See [ticket 16 evidence](16-retrieval-benchmarks.md#saved-measurements-and-exact-commands--2026-10-08).

No comparative latency, throughput, capacity, cache win or HNSW promotion claim is made. Full 60-second warm-up / 180-second / three-repetition runs remain available through the driver; the short paired runs are not substitutes for those quoted-result criteria.

Completed on 2026-10-09. The benchmark API was left healthy on `adflow_benchmark`, Redis enabled, with full-scan retrieval.
