# 22 — Load validated model artifacts and predict candidate batches

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 15, 17, 20, 21

## Scope

Persist internal joblib pipeline with model/feature/data/runtime manifests and checksum. Load once per process with compatibility/prediction checks; implement ordered finite [0,1] batch probabilities and positive-class lookup. Provide an adapter without adding V2 scoring before Phase 4.

## Dependencies

- [15 — Integrate candidate retrieval into recommendation serving](15-retrieval-serving.md)
- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [20 — Train a persisted preprocessing and Logistic Regression pipeline](20-logistic-training.md)
- [21 — Evaluate CTR probabilities against the training base-rate baseline](21-ctr-evaluation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Reload/single/batch parity, order/count preservation, empty batches and unknown categories are tested.
- [ ] Missing/corrupt/incompatible artifacts and invalid probabilities produce a typed unavailable failure; baseline remains usable.
- [ ] Measure feature and batch inference separately; no per-candidate DB access/model reload.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
