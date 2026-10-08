# 05 — Persist recommendations and idempotent request outcomes

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 02, 04

## Scope

Implement the recommendation service: required request-key association, replayable selection/no-ad outcomes, immutable bid/ad snapshot, 24-hour expiry and key/user conflicts. Atomically persist selection/outcome, revalidate eligibility and keep saved score/bid coherent. Recover concurrent uniqueness conflicts and response-loss retries.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)
- [04 — Implement deterministic interest-overlap selection](04-baseline-selector.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Same key/user replays the same selection or no-ad outcome; another user conflicts; expired keys do not create new opportunities.
- [ ] Concurrent requests and commit-then-response-loss yield one durable outcome.
- [ ] Unknown users and required database failures preserve 404/503 semantics; no unsaved success.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
