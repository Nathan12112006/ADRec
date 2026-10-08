# 58 — Explain and modify retrieval and eligibility

Status: ready-for-human
State: open
Type: task
Kind: human-checkpoint
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 17

## Scope

Nathan explains topic vectors, exact/HNSW retrieval, current eligibility, fallback and tie-aware quality, then makes or directs a relevant small change.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explain why faster search alone does not prove a better retrieval pipeline.
- [ ] Verify the change with relevant retrieval checks.
- [ ] Record actual human review and remaining gaps.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
