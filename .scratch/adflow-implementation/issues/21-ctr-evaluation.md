# 21 — Evaluate CTR probabilities against the training base-rate baseline

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 17, 20

## Scope

Implement frozen-pipeline evaluation: primary log loss, ROC-AUC, Brier loss and reliability diagram with bin counts. Compare a training-only constant base rate on identical rows; preserve counts/splits and report final synthetic test honestly.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [20 — Train a persisted preprocessing and Logistic Regression pipeline](20-logistic-training.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Metric fixtures cover single-class evaluation AUC unavailable and explicit binary log-loss labels.
- [ ] Reports/plots distinguish calibration, discrimination and synthetic limitations; no mandatory score/lift.
- [ ] Final-test results do not trigger generator retuning or test-data fitting.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
