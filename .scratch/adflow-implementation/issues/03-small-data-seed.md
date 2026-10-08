# 03 — Generate reproducible configurable entity seeds

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 02

## Scope

Build an explicit seed CLI defaulting to 100 users, 20 advertisers and 1,000 ads with zero history. Support configurable counts including the full entity scale, seeded independent streams, vocabulary/category relationships, active inventory, nonnegative bids and dataset provenance. Define safe repeat invocation and dataset replacement behavior without automatic history overwrite.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Same seed/configuration reproduces entities and references; counts and relationships are checked.
- [ ] Small seed works without FAISS, ML, Redis or experiment artifacts.
- [ ] Existing lifecycle history is not silently cleared; commands and synthetic assumptions are documented.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
