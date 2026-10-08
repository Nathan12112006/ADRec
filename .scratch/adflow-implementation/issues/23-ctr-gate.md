# 23 — Verify and record the CTR-model phase gate

Status: ready-for-agent
State: open
Type: task
Kind: verification
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 17, 21, 22

## Scope

Run the canonical offline data/training/evaluation/artifact tests, save actual quality and inference evidence, and document generation/train/evaluate/reload commands. Record underperformance without hiding it.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [21 — Evaluate CTR probabilities against the training base-rate baseline](21-ctr-evaluation.md)
- [22 — Load validated model artifacts and predict candidate batches](22-ctr-artifact-serving.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Reproduction and all model compatibility/feature checks pass.
- [ ] Reports contain actual metrics, baseline and provenance; no real-world effectiveness claim.
- [ ] Offer the model learning checkpoint and unlock Phase 4 only after the technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
