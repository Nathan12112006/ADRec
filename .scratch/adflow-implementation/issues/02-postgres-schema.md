# 02 — Implement PostgreSQL sessions and initial schema migrations

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 01

## Scope

Add SQLAlchemy session/transaction lifecycle and Alembic migrations for users, advertisers, ads, request outcomes, recommendations and events. Include decimal bids/revenue, UTC timestamps, dataset identity and immutable selection snapshots. Encode request-key uniqueness, event deduplication and referential integrity in PostgreSQL; retain durable history.

## Dependencies

- [01 — Create the backend package and configuration foundation](01-backend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] A fresh isolated database reaches the intended schema via migrations; no startup create_all shortcut.
- [ ] Constraint tests prove duplicate keys/events and invalid relationships cannot bypass persistence rules.
- [ ] Pool/connect/query waits are bounded and failures roll back safely.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
