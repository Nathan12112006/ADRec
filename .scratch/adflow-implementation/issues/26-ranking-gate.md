# 26 — Verify and record the ranking phase gate

Status: ready-for-agent
State: open
Type: task
Kind: verification
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 23, 25

## Scope

Run all ranking and lifecycle regression checks and compare strategies on identical candidate sets. Save algorithm explanation, response examples and actual outcomes without comparing incompatible raw-score averages.

## Dependencies

- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)
- [25 — Persist coherent ranked selections and explicit response context](25-ranked-selection-context.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Formula/batch/tie/replay/accounting/model-failure checks pass.
- [ ] No unsupported auction, blending or score-normalization layer has been added.
- [ ] Offer the ranking learning checkpoint and unlock Phase 5 after this technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
