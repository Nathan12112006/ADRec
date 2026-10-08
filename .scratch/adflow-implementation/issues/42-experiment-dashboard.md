# 42 — Build experiment list and comparison detail views

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 38, 40

## Scope

Display experiment lifecycle, configuration and full-cohort V1/V2 metrics with exposed users, impressions, clicks, CTR, revenue, revenue per exposed user and relative lift.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [40 — Create the React dashboard shell and reliable polling](40-frontend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Show cohort cutoff/as-of/provisional status and null lift when control is zero.
- [ ] Include relevant failure/replay/fallback diagnostics without excluding failed treatment attempts.
- [ ] No browser management controls, significance, winner or rollout claims.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
