# 30 — Collect bounded rolling request and pipeline telemetry

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 07, 26, 29

## Scope

Implement the process-local telemetry needed before experiment results/dashboard: monotonic stage timings, 15-minute rolling retention with count/memory caps, experiment/variant diagnostics, request populations and reset/coverage/drop metadata. Keep durable business events authoritative.

## Dependencies

- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)
- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [29 — Route recommendations with immutable experiment attribution](29-experiment-routing.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests separate new selections, no-ad, replays, errors and event endpoints; no mean-of-percentiles aggregation.
- [ ] Bounds, restarts, unknown attribution and missing telemetry are explicit rather than zero/perfect metrics.
- [ ] Capture error/fallback populations even without a durable recommendation when possible; label incomplete outages.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
