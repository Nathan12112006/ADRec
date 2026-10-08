# 43 — Build the rolling performance and dependency view

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 38, 40

## Scope

Display rolling 15-minute request/population latency, throughput, failures, cache counters and dependency capabilities using GET metrics.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [40 — Create the React dashboard shell and reliable polling](40-frontend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Disclose actual coverage, process reset/drop/cap limitations and histogram approximation.
- [ ] Separate newly selected responses, replay, no-ad, failures and events.
- [ ] Do not present process-local metrics as a distributed monitoring system or cache-hit ratio as overall request success.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
