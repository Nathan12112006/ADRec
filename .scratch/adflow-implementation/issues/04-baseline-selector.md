# 04 — Implement deterministic interest-overlap selection

Status: ready-for-agent
State: active
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02

## Scope

Add baseline selection outside routes over active ads from active advertisers. Order by distinct shared-interest count descending, bid descending and ad ID ascending; preserve zero-bid eligibility. Keep selection separable from persistence for later retrieval integration.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Focused tests cover interest overlap, deterministic ties, empty interests, zero bids and inactive inventory.
- [ ] Empty eligible inventory returns a no-ad result rather than a fabricated winner.
- [ ] Explain scan time/space costs; no model invocation or invented predicted CTR.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
