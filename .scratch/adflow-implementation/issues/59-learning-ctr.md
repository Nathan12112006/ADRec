# 59 — Explain and modify the CTR pipeline

Status: ready-for-human
State: open
Type: task
Kind: human-checkpoint
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 23

## Scope

Nathan explains synthetic exposure, features, leakage prevention, chronological splits, probability evaluation and serving artifacts, then makes or directs a small model-pipeline change.

## Dependencies

- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explain the baseline and what synthetic test results can support.
- [ ] Verify the change and training/serving consistency.
- [ ] Record actual human review; do not infer understanding from acceptance of recommendations.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
