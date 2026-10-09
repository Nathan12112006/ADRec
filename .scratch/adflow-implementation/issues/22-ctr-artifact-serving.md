# 22 — Load validated model artifacts and predict candidate batches

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Reload/single/batch parity, order/count preservation, empty batches and unknown categories are tested.
- [x] Missing/corrupt/incompatible artifacts and invalid probabilities produce a typed unavailable failure; baseline remains usable.
- [x] Measure feature and batch inference separately; no per-candidate DB access/model reload.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implementation evidence (2026-10-08):

- Started from `97223abc3c1f5b3735ec55e2808f668e398b70ae` after dependencies 15, 17, 20 and 21 were done. Nathan confirmed the public adapter and application-startup test seams. TDD exercised missing adapter behavior before implementation, then ordered reload/single/batch predictions, unknown categories, empty input, failures and baseline HTTP availability.
- Added an explicit offline packaging command that combines the frozen joblib pipeline and its exact evaluation report. The bundle includes model, feature, source-data, dependency and Python manifests, evaluation metrics, artifact checksum and content identity. Loading validates these and the persisted prediction fixture before use. Evaluation and serving share the frozen loader and select the probability column by positive class label.
- Added a process-resident adapter and optional startup configuration. Every nonempty batch builds shared features once and calls the pipeline once; no database access or artifact reload occurs inside predictions. Empty batches need no model. Missing, corrupt, incompatible or invalid-output models expose safe typed `ctr_unavailable`/503 failures; the existing baseline route remains usable. No Phase 4 scoring/routing is introduced. A runtime smoke check found the startup warning needed the existing JSON formatter's structured context; the fix and formatted-event assertion are included.
- Packaged the retained full ticket 20 model and ticket 21 evaluation into ignored `artifacts/ctr-ticket22-native`. Model identity remains `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`; pipeline SHA-256 remains `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`; serving bundle identity is `0e2322403f52bb7a9ddcbb0115317bc642593428daee8cc693ec9fbfff5d2345`. [Manifest](../evidence/ticket22/native-bundle-manifest.json) retains complete provenance and evaluation evidence. Packaging never fits or retunes the model.
- [Native smoke](../evidence/ticket22/native-smoke.json) and [Docker smoke](../evidence/ticket22/docker-smoke.json), reproduced by [runtime-smoke.py](../evidence/ticket22/runtime-smoke.py), train/evaluate/package a disposable fixture through public offline commands, verify repeat manifest equality and pipeline checksums, ordered finite batch/single parity to `1e-12`, unknown/empty inputs, startup residency after deleting files, and fresh-startup failure after deletion. Docker CPython 3.12.15 also rejects the foreign native CPython 3.10.11 bundle. Final image: `sha256:ddca90a4dbbf205bf9f9a45272e1c1c93c4a3231f095d4973e228de8d7548160`.
- [Measurement](../evidence/ticket22/inference-measurement.json), reproduced by [measure-inference.py](../evidence/ticket22/measure-inference.py): Windows CPython 3.10.11, AMD64 Family 23 Model 104, 16 logical CPUs, one native thread, one caller, 10 warmups and 50 samples per size. For 1/50/500 candidates, feature median/p95 milliseconds were `0.0844/0.1591`, `0.4763/0.7299`, `4.1171/6.5782`; batch inference median/p95 were `6.3519/8.7574`, `7.4340/11.6554`, `9.5967/13.8785`. One-time load was 66.7924 ms. These are local component costs including validation, excluding retrieval/database/HTTP/load; other verification processes were active. No end-to-end latency or speedup claim is made.
- Focused adapter/evaluation/baseline tests: 41 passed. Full PostgreSQL-enabled suite against disposable `adflow_ticket22_test`: **538 passed** in 186.87 seconds. After the final logging change, all 16 adapter/startup tests passed again. Sandboxed TestClient attempts stalled and were interrupted; elevated verification completed. Alembic reported no new operations; wheel/sdist build and offline lockfile verification passed.
- Independent final Standards review: 0 documented violations, 0 outstanding heuristic findings (validator naming concern fixed). Independent final Spec review: 0 actionable findings. This ticket makes no human explain-and-modify checkpoint claim.
- Final clean mypy run (`--no-incremental`): 91 source files passed. Ruff lint and formatting checks passed. An earlier concurrent incremental run reported stale unused-ignore diagnostics; the final complete typecheck resolved them without suppressing checks.
