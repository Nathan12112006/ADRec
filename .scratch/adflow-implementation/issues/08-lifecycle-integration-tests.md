# 08 — Verify lifecycle races, expiration and dependency failures

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 03, 07

## Scope

Build isolated PostgreSQL integration fixtures and controllable-clock/concurrency scenarios. Exercise the complete lifecycle beyond unit-level prechecks, including response-loss replay, no-ad replay, mismatched keys/users, inactive inventory, unknown IDs and commit failure.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Real PostgreSQL tests cover racing keys/events and exact 24-hour boundaries including duplicates after expiry.
- [ ] Changed bids/eligibility and click ordering retain coherent saved state.
- [ ] Test execution cannot reset the development database; commands and observed results are retained.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
