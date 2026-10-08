# 09 — Package the backend and document Phase 1 setup

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 03, 07

## Scope

Add backend Dockerfile and backend/PostgreSQL Compose operation, preserving local-backend development. Document explicit migration/seed preparation followed by ordinary startup, lifecycle curl/API walkthrough and test commands. Keep large history, model training and later services out of startup.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Verify fresh-container and local-backend startup using the documented commands.
- [ ] Document volumes/settings and isolated test setup; no silent data replacement or model/history generation.
- [ ] README contains actual Phase 1 behavior and limitations, not future capability claims.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
