# CTR-model gate evidence

The fresh [reproduction](reproduction.json) passed on Windows CPython 3.10.11.
Starting from retained frozen users/ads, it regenerated the original 1,000,000
historical exposures and 22,351 clicks, rebuilt all five shared features and
chronological splits, trained, evaluated, packaged and reloaded the pipeline.
Complete manifests and evaluation report, generated data hashes, persisted pipeline
checksum and serving bundle identity equal the retained tickets 18–22 artifacts.
All retained input files have unchanged before/after SHA-256 hashes. No configuration
or generator change followed inspection of final-test results.

Dataset: `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`.
History: `2ed92061-8b66-59b4-8a1b-509f340d47d0`.
Model: `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`.
Bundle: `0e2322403f52bb7a9ddcbb0115317bc642593428daee8cc693ec9fbfff5d2345`.
Pipeline SHA-256: `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`.

The original history seed is 18; the entity seed is 180018. The chronological
train/validation/test counts are 700,000/150,000/150,000, with 15,606/3,408/3,337 clicks.
The original C candidates are 0.1/1/10; validation-only log loss again selects C=0.1.
Preprocessing and coefficients fit training data only. The final test is scored by
the frozen selected model. Generation, features, training, evaluation and package/
reload wall costs were 84.742s, 48.011s, 15.487s, 8.542s and 2.715s respectively.
These include validation/I/O/startup, ran alongside verification, and are not serving
benchmarks. Entity generation/database export were not repeated in this gate.

## Probability quality

The constant baseline is fitted only from training labels: 15,606/700,000 =
0.022294285714285715. Identical examples are scored by each predictor within a split.

| Split | Predictor | Rows | Clicks | Observed CTR | Log loss | ROC-AUC | Brier loss |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Validation | Model | 150000 | 3408 | 0.02272 | 0.1054235657 | 0.6386663444 | 0.0220482393 |
| Validation | Baseline | 150000 | 3408 | 0.02272 | 0.1084481153 | 0.5 | 0.0222039828 |
| Test | Model | 150000 | 3337 | 0.0222466667 | 0.1041731584 | 0.6259317678 | 0.0216205760 |
| Test | Baseline | 150000 | 3337 | 0.0222466667 | 0.1066584995 | 0.5 | 0.0217517548 |

The model improves these metrics against the constant on this synthetic cohort; no
minimum score, lift or calibration improvement is inferred. The reproduced full
report equals [ticket 21 JSON](../ticket21/report.json), including all provenance,
split boundaries, class counts and reliability bins. Generated PNG hashes match its
manifest: [validation](../ticket21/reliability-validation.png),
[test](../ticket21/reliability-test.png). Underperforming or single-class results
would remain reportable rather than being hidden or turned into invented scores.
Unknown categories are accepted structurally; their quality is not established.
These data do not establish real-user effectiveness or entirely unseen-user/ad
generalization. The already-inspected final test must not become a model-selection set.

## Separate inference costs

[Raw measurement](inference-measurement.json) uses the reproduced full bundle, one
frozen user and the first 1/50/500 frozen ads. Hardware is AMD64 Family 23 Model 104,
16 logical CPUs, Windows CPython 3.10.11. One native thread/caller, 10 warmups and
50 measurements per size; one-time model load was 24.656 ms.

| Candidates | Feature median / P95 ms | Batch inference median / P95 ms |
| ---: | ---: | ---: |
| 1 | 0.0353 / 0.0495 | 2.5264 / 3.0092 |
| 50 | 0.2513 / 0.3046 | 2.7255 / 3.2939 |
| 500 | 2.2736 / 3.5749 | 3.5843 / 5.4248 |

Feature timing includes shared feature validation and matrix construction; inference
includes pipeline work and output validation. Retrieval, database access, HTTP and
artifact loading are excluded. Other verification processes were active. Differences
from ticket 22 timings are not an optimization or speedup result. The prediction
adapter accesses no database or artifact files per candidate and calls the fitted
pipeline once per nonempty batch. Dense arithmetic/storage is O(C*F), with O(F)
coefficients for C candidates and F encoded features; sparse encoding changes costs.

## Contract checks and runtime evidence

| Contract | Canonical existing checks |
| --- | --- |
| Reproducible independent history, binary outcomes, frozen eligible snapshots, no live writes | `test_history_outcomes.py`, `test_history_artifacts.py`, `test_history_cli.py`, integration `test_history.py` |
| Allowed five feature inputs, distinct overlap, category match, zero-interest/missing/unknown values, chronological labels/boundaries/version | `test_ctr_features.py`, `test_ctr_dataset.py` |
| Training-only preprocessing, validation selection, unread final test, adequate labels, convergence, checksums/runtime metadata | `test_ctr_training.py` |
| Frozen scoring, same-row training-only baseline, actual metrics/bin counts, single-class AUC unavailable, reproducibility | `test_ctr_evaluation.py` |
| Reload/single/batch parity, ordered counts, label-1 lookup, empty/unknown input, resident startup, unavailable/corrupt/incompatible/invalid output | `test_ctr_serving.py` |
| Baseline HTTP serving with absent/missing/corrupt model | integration `test_ctr_availability.py` |

[Native smoke](native-smoke.json) and [Docker smoke](docker-smoke.json) pass repeated
small-fixture train/evaluate/package commands and resident startup predictions after
source-file removal, then verify unavailable state on a fresh startup. Docker CPython
3.12.15 rejects the native CPython 3.10.11 bundle before activation. Artifacts are
trusted project-generated joblib only; checksum identity is not a security boundary.
Docker image: `sha256:0ff02c67b084a91fbbdff7c8005efb26853b333723b8f29155db7f5699b7702f`.
Native/container identities need not match; each runtime independently reproduces its
own fixture. The Docker fixture is not a full-scale throughput/quality benchmark.

Exact [commands](commands.md) include generation, feature preparation, training,
evaluation, packaging/reload, canonical tests and final checks. The separate human
[ticket 59](../../issues/59-learning-ctr.md) remains open: technical evidence does not
certify Nathan's explanation or verified modification.

Final checks on 2026-10-08: **115 focused tests passed** in 59.82 seconds;
**538 full backend tests passed** in 124.28 seconds, including PostgreSQL integration
against isolated `adflow_ticket23_test`. Strict mypy passed 91 source files; Ruff
lint/format passed; Alembic reported no new upgrade operations. Wheel/sdist builds,
offline lock validation (65 packages), Docker configuration/build/smoke and evidence
script lint/format passed. No application changes or new test seams were needed.

Independent final reviews: Standards 0 documented violations/0 heuristic findings;
Spec 0 actionable findings. The technical gate is complete and unblocks Phase 4;
ticket 59 remains open for the offered human checkpoint. The verification PostgreSQL
server stopped cleanly; databases and artifacts are retained.
