# 46 — Implement reproducible Locust benchmark workloads

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 32, 45

## Scope

Pin Locust and implement separate recommendation-only durable-write and full recommendation/impression/click workloads. Use reproducible uniform/hot users, unique opportunity keys and accepted semantic response classification.

## Dependencies

- [32 — Build reproducible API-driven demo traffic and edge scenarios](32-live-simulator.md)
- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Closed-loop load has no think time; user count is never labeled achieved RPS.
- [ ] Transport, HTTP, timeout and semantic errors are counted distinctly.
- [ ] Lifecycle requests honor impression-before-click; retries and replay populations remain identifiable.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
