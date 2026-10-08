# 49 — Execute the controlled performance comparison matrix

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
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

- [ ] Save raw artifacts and provenance for each attempted run; report incomplete or failed configurations without extrapolation.
- [ ] Quoted results have three full measured repetitions and comparable populations.
- [ ] Any 100k-ad or HNSW promotion claim is supported by actual dataset size, tie-aware recall and full-retrieval p95 evidence.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
