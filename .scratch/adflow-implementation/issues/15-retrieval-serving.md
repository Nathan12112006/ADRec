# 15 — Integrate candidate retrieval into recommendation serving

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 07, 10, 13, 14

## Scope

Replace the baseline all-ad selection input with the bounded retrieved candidate set, preserving ranking semantics, durable replay and no-ad behavior. Persist retrieval context with the selection and separate vector/metadata/ranking/database timings.

## Dependencies

- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [13 — Implement current eligibility filtering and exact fallback](13-eligibility-backfill.md)
- [14 — Add the HNSW candidate-retrieval comparison](14-hnsw-option.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] End-to-end tests prove downstream ranking uses at most the configured candidate count.
- [ ] Replay never reretrieves; index/model-independent baseline serving and exact fallback work.
- [ ] Snapshot/eligibility changes cannot save stale eligibility or mismatched score/bid fields.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
