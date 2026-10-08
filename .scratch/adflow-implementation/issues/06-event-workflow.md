# 06 — Record client impressions and clicks with atomic accounting

Status: ready-for-agent
State: active
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 02, 05

## Scope

Implement impression/click services by recommendation ID. Derive attribution server-side; require impression before first click; accept first events strictly within the creation-based 24-hour window. Deduplicate before expiry rejection and credit the captured bid once per first accepted click.

## Dependencies

- [02 — Implement PostgreSQL sessions and initial schema migrations](02-postgres-schema.md)
- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Concurrent duplicates produce one impression/click and one decimal revenue credit.
- [ ] Click-before-impression can recover via confirmation/retry; accepted duplicates remain safe after expiry.
- [ ] Bid edits/deactivation do not rewrite existing attribution; failed commits accept no event/accounting effect.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
