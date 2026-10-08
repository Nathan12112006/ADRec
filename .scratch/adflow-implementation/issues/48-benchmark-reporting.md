# 48 — Produce honest latency and workload reports

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 30, 45, 47

## Scope

Report client HTTP, server and stage timings separately with mean/p50/p95/p99 by response population, opportunity/request throughput, CPU/memory, error categories and actual coverage.

## Dependencies

- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)
- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [47 — Build controlled benchmark execution and provenance capture](47-benchmark-runner.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Never average percentiles across repetitions; preserve per-run results and explain any aggregation.
- [ ] Disclose server histogram approximation and bounded telemetry drops/reset.
- [ ] Reports distinguish durable selection work from lifecycle/event work, replay and no-ad traffic.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
