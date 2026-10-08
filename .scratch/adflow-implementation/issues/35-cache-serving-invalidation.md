# 35 — Integrate cache fallback and post-commit invalidation

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33, 34

## Scope

Use cache-aside profile reads while retaining PostgreSQL authority for outcomes, events, experiments, current eligibility and bids. On a Redis read failure bypass remaining cache work for that request; failed cache writes cannot break otherwise valid database work.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [34 — Implement bounded Redis profile-cache access](34-profile-cache-adapter.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Commit profile changes before invalidation; document the accepted stale-repopulation race.
- [ ] Dataset replacement pauses traffic and changes the cache namespace; no public profile-edit API is introduced.
- [ ] Integration tests prove Redis outage preserves valid requests and database outage still returns 503.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
