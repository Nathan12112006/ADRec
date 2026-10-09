# 23 — Verify and record the CTR-model phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Reproduction and all model compatibility/feature checks pass.
- [x] Reports contain actual metrics, baseline and provenance; no real-world effectiveness claim.
- [x] Offer the model learning checkpoint and unlock Phase 4 only after the technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Technical verification on 2026-10-08, starting at `76696d39365c20c2712d849547d86757531604e5`:

- Dependencies 17, 21 and 22 were done. No application change or new test seam was needed; existing agreed feature/training/evaluation/adapter/application seams cover the canonical contract.
- [Gate results](../evidence/ticket23/results.md) and [exact reproduction/check commands](../evidence/ticket23/commands.md) retain actual metrics, identities, costs, compatibility checks and limitations. README now links the gate and explains Logistic Regression, regularization, leakage safeguards, synthetic limits and O(C*F) prediction/storage versus O(F) coefficients.
- [Fresh full reproduction](../evidence/ticket23/reproduction.json) passed from frozen ticket 18 source snapshots, regenerating **1,000,000 exposures / 22,351 clicks**, rebuilding features and 700,000/150,000/150,000 chronological splits, retraining with unchanged validation-only regularization selection, evaluating the frozen choice, packaging and reloading. Exact data/model/bundle manifests, hashes and evaluation output match retained tickets 18–22. All retained input hashes are unchanged. Entity generation/database export were not repeated; their prior verification remains linked through ticket 18 provenance. Outputs are retained under ignored `artifacts/ctr-ticket23-reproduction/`, with no resets or live-table writes by the auditor.
- Model identity remains `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`, bundle `0e2322403f52bb7a9ddcbb0115317bc642593428daee8cc693ec9fbfff5d2345`, pipeline SHA-256 `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`. Full report/PNG hashes equal ticket 21's retained outputs. Training-only base rate is 15,606/700,000. On 150,000 final-test rows / 3,337 clicks, model versus baseline log loss is **0.1041731584 / 0.1066584995**, AUC **0.6259317678 / 0.5**, Brier loss **0.0216205760 / 0.0217517548**. Validation metrics, sample counts, class counts, boundaries and reliability bins remain visible. No generator/settings changes, final-test tuning, real-world effectiveness or guaranteed calibration/lift claim is made; unknown-category handling is structural, not evidence of its predictive quality.
- [Fresh component timings](../evidence/ticket23/inference-measurement.json) separate feature construction from batch inference for 1/50/500 candidates, one thread/caller, 10 warmups and 50 samples, AMD64 Family 23 Model 104/16 logical CPUs, Windows CPython 3.10.11. Feature median/P95 milliseconds: `0.0353/0.0495`, `0.2513/0.3046`, `2.2736/3.5749`; batch inference: `2.5264/3.0092`, `2.7255/3.2939`, `3.5843/5.4248`. Load: 24.656 ms. Other checks were active; excludes retrieval/DB/HTTP/loading and does not establish speedup or request-latency targets. Adapter uses one pipeline call and no per-candidate DB/file access.
- [Native](../evidence/ticket23/native-smoke.json) and [Docker](../evidence/ticket23/docker-smoke.json) smoke pass repeatable small-fixture train/evaluate/package commands, ordered finite batch/single predictions, startup residency, fresh-startup failure after deletion and Docker rejection of a foreign native bundle. Native/container CPython: 3.10.11/3.12.15. Docker image `sha256:0ff02c67b084a91fbbdff7c8005efb26853b333723b8f29155db7f5699b7702f`. No cross-runtime artifact equality or full-scale Docker performance claim.
- Canonical focused tests: **115 passed in 59.82s**. Full regression: **538 passed in 124.28s**, PostgreSQL enabled with isolated `adflow_ticket23_test`. Mypy: **91 source files clean**; Ruff lint/format pass; Alembic: **no new upgrade operations**; wheel/sdist, offline lock check (**65 packages**), Docker config/build and evidence script checks pass. No check failure required a production change.
- Offered [ticket 59](59-learning-ctr.md): explain excluded features/leakage/base-rate comparison, then direct a small development-data change and verify training/serving consistency. The already-inspected final test cannot become a tuning set. Ticket 59 remains open; no explanation, modification or understanding is certified. Phase 4's technical dependency will unlock only when this gate is marked done after review.

### Standards

Independent read-only review against task-start `76696d39365c20c2712d849547d86757531604e5`, including untracked gate evidence: **0 documented violations, 0 heuristic findings**. Tracker/domain conventions, exact command/results reporting and open human-checkpoint separation pass. Counts, identities, metrics and timing values agree with JSON; frozen-source reuse and native/container scope are accurately disclosed. No unsupported effectiveness, performance or learning claims were found. No tests or heavy reproduction were repeated by the reviewer.

### Spec

Independent read-only review: **0 actionable findings**. Reproduction, quality/baseline/provenance, compatibility/feature checks, separate inference evidence and documented commands satisfy ticket 23. The learning checkpoint is offered while remaining open. No missing requirement or scope creep prevents completion.

Review total: Standards 0; Spec 0; neither axis has an outstanding issue. All technical acceptance criteria pass; **Phase 3's technical gate is complete and ticket 24/Phase 4 is unblocked**. Ticket 59 remains open for actual human work. PostgreSQL started for this verification was stopped cleanly; all databases, original artifacts and new reproduction outputs remain retained. Final whitespace and saved-report provenance checks passed. The implementation skill's commit is on the current `main` branch.
