# What CTR model and evaluation contract are credible for synthetic data?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 03

## Question

Choose the minimal features, label definition, training/evaluation split, leakage safeguards, probability evaluation metrics, serialization/loading contract, batch prediction interface, and missing-model behavior. Distinguish training quality from serving performance and real-world effectiveness. Decide whether historical aggregate features earn their complexity and how model and feature versions remain compatible.

## Comments

The round notes below are chronological history. The final contract is recorded under Answer.

### Confirmed preprocessing, evaluation, and serving choices

- Nathan accepted a shared feature builder and persisted preprocessing/Logistic Regression pipeline, categorical encoding with explicit unknown handling, regularization selected using validation data, and no initial class balancing or negative undersampling.
- Nathan accepted log loss as primary, ROC-AUC, Brier loss, and a calibration plot with sample counts, compared against training base-rate predictions. Require both classes in training; report AUC unavailable for single-class evaluation subsets. No target score or guaranteed improvement.
- Nathan accepted ordered batch prediction, model/feature versions, one pipeline load per process, and internally produced joblib artifacts with provenance/compatibility manifests and matching dependencies. Reject incompatible artifacts.
- Nathan accepted 503 for requests requiring CTR ranking when the model is missing, corrupt, or incompatible. Baseline ranking remains available; do not silently substitute it within a CTR request or invent probabilities.
- Supporting primary-source findings: [CTR model and evaluation options](../research/ctr-model-options.md).
- Q8 completion checks were not answered. Keep the ticket claimed and unresolved pending that decision.

### Confirmed feature and training choices

- Nathan accepted shared-interest count, category-match flag, ad category, device type, and age group as initial features.
- Exclude bid, user/ad IDs, experiment variant, and hidden generator preferences from model inputs. Bid is a ranking input, not a CTR feature in this version.
- Nathan accepted omitting historical ad/category CTR and user activity features initially; add time-sensitive aggregates only if later evidence justifies them.
- Train via an explicit offline command using the agreed historical artifacts and chronological splits, save a versioned artifact, and load it for serving. No request-time training or automatic ingestion of live experiment events.
- Preprocessing, metrics, model availability, artifact compatibility, and completion checks remain open.

Claimed at Nathan's request on 2026-10-07. Starting the live feature/evaluation/serving decision session, using the resolved synthetic-world contract and primary-source scikit-learn research.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted Q8: reproducible training/evaluation, artifact reload checks, batch/single prediction agreement, unknown-category and empty-interest tests, feature-version validation, model-failure tests, separate inference measurements, and honest reporting of underperformance. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. [CTR model and evaluation options](../research/ctr-model-options.md) supplies primary-source support. This is a model contract, not a trained model or an evaluation result.

### Label and initial features

Predict P(click | displayed ad, user/ad context). Use one historical impression as a labeled example: 1 if its generated click outcome is positive, otherwise 0. Do not label a failed live event submission as a genuine nonclick or ingest live events automatically.

Initial features are:

- Count of distinct interests shared by the user and ad target interests.
- Whether the ad category is included in the user's interests.
- Ad category.
- User device type.
- User age group.

Exclude bid, user/ad IDs, experiment variant, hidden generator preferences, true generating probability, and the outcome itself. Bid belongs in ranking. Historical ad/category CTR and user activity features are deferred because they require point-in-time computation and matching serving state.

Use one deterministic shared feature builder in offline training/evaluation and online batch inference. Keep source profile/ad snapshots linked to historical data so later database edits do not rewrite historical features. Empty interests give zero overlap and a false category match. Encode categorical features with explicit missing-value conventions and unknown handling; unseen categories must not change feature shape or crash inference. Their acceptance does not establish prediction quality for unseen groups.

### Training and preprocessing

Use explicit offline training and evaluation commands. Retain the synthetic-world ticket's chronological 70/15/15 training/validation/final-test split, grouping every impression with its label.

Fit categorical encoding and numeric preprocessing only on training data and persist them with regularized Logistic Regression as one fitted pipeline. Start without class balancing or negative undersampling. Select from a small documented set of regularization settings using validation data, record convergence and parameters, then freeze the selected pipeline before final test evaluation. Do not tune using final-test outcomes, retrain during requests, or automatically combine live experiment events with offline training data.

Require both classes in the training split; reject an inadequate training dataset with an actionable error rather than producing a misleading classifier. Report class counts and convergence failures. No training step reads hidden preferences or generator probabilities as features.

### Evaluation and baseline

Use log loss as the primary metric. Also report ROC-AUC, Brier loss, and a calibration/reliability plot with bin sample counts. Fit a constant base-rate prediction using only training labels and compare it with the model on identical validation/test examples.

Record sample counts, positive counts, observed CTR, split boundaries, dataset provenance, and model settings. AUC is unavailable for a single-class evaluation subset; do not turn it into zero or a fabricated score. Explicit binary labels allow meaningful log-loss reporting in that case; report Brier loss and the sample limitation too.

Probability scoring, discrimination, and calibration are related but distinct: lower log loss alone does not prove better calibration. Do not promise a target AUC, accuracy, or lift. Underperforming results remain visible; never modify the generator after inspecting final test outcomes to force an improvement. Later calibration work, if justified, needs a separate development-data plan without consuming the final test for fitting.

Evaluation establishes performance on later outcomes from this designed synthetic world. It does not demonstrate real-user effectiveness or generalization to entirely unseen users/ads. Class imbalance is not addressed by relying on accuracy as the headline result.

### Batch prediction and artifacts

The CTRModel interface predicts a batch for one user and an ordered candidate collection, returning one finite probability in [0,1] per candidate in the same order, with model/feature versions. A convenience single-ad method may delegate to the batch path. An empty candidate batch returns an empty result without a model call.

Locate the positive label 1 using the estimator's class labels; validate the expected binary label set rather than blindly taking an output column. Build candidate features together and call the saved pipeline once for the batch. Do not load artifacts or issue per-candidate database lookups in the prediction loop.

Load the complete pipeline once per serving process. Use joblib artifacts produced by the project's own offline command, not arbitrary uploaded files. Pair the artifact with a manifest containing model and feature-schema versions, exact feature definitions, label definition, training dataset/generator provenance, split boundaries, hyperparameters, dependency/runtime versions, evaluation metrics, and checksum. Validate compatibility and a prediction fixture before activation. A checksum detects accidental changes; it does not make an untrusted artifact safe.

Pin and verify matching dependencies; cross-version scikit-learn loading is unsupported. Incompatible feature or runtime changes require a compatible rebuild/retraining rather than silent reuse. Serving does not change the active artifact midway through a candidate batch. An explicit restart/reload activates a validated version; automatic online learning is outside scope.

### Model-unavailable behavior

Requests requiring CTR ranking return 503 when the model is missing, corrupt, incompatible, or cannot produce valid probabilities. Do not invent a CTR or silently substitute the baseline algorithm. Baseline ranking remains available without the model. Experiment assignment and reporting must preserve this behavior rather than labeling baseline executions as successful CTR treatment; the experiment ticket owns cohort/error reporting details.

### Completion checks and implementation explanation

1. Reproduce offline training/evaluation from documented commands with the declared seed/configuration and chronological splits; record actual metrics and baseline comparisons.
2. Verify shared feature semantics, allowed input columns, zero-interest behavior, category-match calculation, unknown/missing categorical values, and stable feature versions.
3. Test saved/reloaded prediction agreement, batch/single agreement within declared numerical tolerance, candidate order/count preservation, empty batches, positive-class lookup, and finite probability bounds.
4. Test missing/corrupt/incompatible artifacts, invalid training labels, and CTR-required 503 behavior while baseline serving remains available.
5. Measure feature-building and batch-inference latency separately from retrieval, end-to-end latency, and offline predictive quality. Report candidate count, runtime, and hardware; no latency target or improvement is presumed.
6. Explain Logistic Regression conceptually: a weighted feature sum passed through a sigmoid yields a click probability; regularization limits coefficient fitting. For C candidates and F encoded features, dense prediction work is O(C*F), with O(C*F) feature-batch storage and O(F) coefficients; sparse storage changes the practical cost. Training costs depend on examples, encoding, solver, and convergence. Categorical expansion, feature building, and request concurrency may dominate small-model inference.

The ranking ticket owns score formulas and use of predicted CTR; the experiment ticket owns immutable algorithm/model attribution. No additional decision ticket is needed. No model or tests were run during this planning resolution.
