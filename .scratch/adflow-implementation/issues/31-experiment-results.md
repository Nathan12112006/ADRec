# 31 — Implement cohort-based experiment result aggregates

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 26, 29, 30

## Scope

Add results queries/API using recommendation creation cohorts and one as-of cutoff. Aggregate deduplicated exposed users/impressions/clicks/captured-bid revenue, recommendation/attempt/fallback/error diagnostics and separate latency populations; return null undefined ratios/lift.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [29 — Route recommendations with immutable experiment attribution](29-experiment-routing.md)
- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests reconcile counts/revenue with durable events and cover zero denominators/control, late events, stop/drain maturity and deduplication.
- [ ] Provisional/synthetic/coverage/context labels are returned; failed reads are errors, not fabricated empty data.
- [ ] No significance tests, winner declaration, selective fallback exclusion or raw-score comparison.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
