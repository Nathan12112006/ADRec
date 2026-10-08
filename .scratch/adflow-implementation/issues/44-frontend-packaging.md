# 44 — Package and verify the complete read-only dashboard

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 38, 41, 42, 43

## Scope

Add frontend Docker/service configuration and document dashboard startup, API connectivity and demo walkthrough. Perform focused UI/build and API integration checks.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [41 — Build the live overview dashboard](41-overview-dashboard.md)
- [42 — Build experiment list and comparison detail views](42-experiment-dashboard.md)
- [43 — Build the rolling performance and dependency view](43-performance-dashboard.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Production frontend build succeeds and Compose exposes the documented application.
- [ ] Verify polling failure recovery, paused/hidden states and responsive accessibility.
- [ ] Use synthetic live traffic to reconcile dashboard values and save actual validation evidence.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
