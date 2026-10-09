# 50 — Profile measured bottlenecks and verify justified improvements

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 45, 49

## Scope

Use recorded measurements to identify the relevant bottleneck, apply a bounded justified improvement if needed, and rerun the affected comparison under matched conditions.

## Dependencies

- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [49 — Execute the controlled performance comparison matrix](49-benchmark-matrix.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Explain the measured cause and no-change decision; retain run evidence.
- [x] No optimization was applied from intuition; the short smoke does not localize a specific component enough to justify one.
- [x] Close with a measured no-change conclusion; no speedup is claimed.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Claimed by Codex on 2026-10-09 after dependencies 45 and 49 were complete.

## Measured no-change conclusion

The matched 10-user smoke completed with zero errors across full-scan, Flat, HNSW, Redis-on/off, uniform/hot access and both HTTP workloads. It uses only a 1-second warm-up and 3-second measurement, so it cannot identify a stable bottleneck or justify an optimization.

The separate fast-ramp diagnostics attempted 100 and 500 users against a single Uvicorn worker. At 500 users, the API container reached about 110% CPU, the 3-second measurement logged more than 1,300 request timeouts in recommendation-only, the metrics observer timed out, and no new selections completed. At 100 users, elevated timeouts also appeared. This points to the current single API worker becoming saturated under the rapid 100-users-per-second ramp; it does not isolate retrieval, Redis, database writes or Python CPU as the root cause. The run was a smoke, not the agreed steady-state workload.

No code optimization was made. The current evidence cannot support before/after results for a specific change, and changing retrieval/cache behavior by intuition risks trading away correctness or quality. Use the documented 60-second warm-up, 180-second measurement and three repetitions at 10 users per second before choosing a bottleneck. Existing 100k-ad results in ticket 16 continue to disqualify HNSW promotion, so Flat remains the retrieval default. No correctness regression was needed for this no-change conclusion.

Evidence: `artifacts/benchmarks/ticket49-matrix-smokes-final/` contains the 10/100/500 diagnostic reports; `artifacts/benchmarks/ticket49-paired-10/` contains the matched clean-baseline smoke reports.

Completed on 2026-10-09 with no optimization.
