# 39 — Expose overview and performance summary APIs

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 30, 31, 38

## Scope

Implement read-only GET analytics/overview and GET metrics using durable business aggregates and bounded process-local telemetry. Reuse experiment result APIs; return summary data rather than raw event history.

## Dependencies

- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)
- [31 — Implement cohort-based experiment result aggregates](31-experiment-results.md)
- [38 — Verify and record the Redis phase gate](38-cache-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Overview covers the current dataset's live records; experiment summaries retain full cohorts.
- [ ] Responses include as-of time, window, units, coverage and provisional/null states.
- [ ] Tests reconcile totals with accepted events and distinguish missing telemetry from zero activity.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
