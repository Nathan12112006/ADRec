# 60 — Explain and modify ranking economics

Status: ready-for-human
State: open
Type: task
Kind: human-checkpoint
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 26

## Scope

Nathan explains V1/V2, predicted CTR times bid, tie-breaking and coherent snapshotting, then makes or directs a small ranking change.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explain units and why no second auction rescoring occurs.
- [ ] Verify deterministic behavior and model failure handling.
- [ ] Record actual human participation and any unresolved gaps.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
