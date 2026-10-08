# 20 — Train a persisted preprocessing and Logistic Regression pipeline

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 17, 19

## Scope

Add offline training with training-only fitted preprocessing and regularized unweighted Logistic Regression. Select a small declared regularization set using validation only; require both training classes, check convergence and freeze the chosen pipeline. No request-time training or negative undersampling.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [19 — Build shared CTR features and chronological splits](19-features-splits.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Reproducible command records parameters, class counts, dependency versions and split identity.
- [ ] Insufficient labels/convergence problems are actionable; final test cannot influence selection.
- [ ] The whole fitted pipeline is exportable for a shared serving path.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
