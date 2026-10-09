# 21 — Evaluate CTR probabilities against the training base-rate baseline

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Metric fixtures cover single-class evaluation AUC unavailable and explicit binary log-loss labels.
- [x] Reports/plots distinguish calibration, discrimination and synthetic limitations; no mandatory score/lift.
- [x] Final-test results do not trigger generator retuning or test-data fitting.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-08

Claimed ticket 21 after dependencies 17 and 20 were done; task-start commit `99c9b5c7c9138ae00aae74f6540d35ac0753b257`, clean working tree. Nathan confirmed the TDD seams: public probability metrics and the offline evaluation command/output report, including reliability plots. Red/green cycles covered unavailable single-class AUC with explicit binary log loss, reliability-bin counts/endpoints, invalid metric inputs, frozen artifact evaluation, and the Markdown table layout. Added `app/ctr/evaluation.py`, 22 focused tests, Matplotlib 3.10.8 with its locked dependencies, README setup/interpretation guidance and reproducibility scripts/evidence.

Evaluation loads the complete frozen project pipeline once, validates its model/content/checksum/schema/runtime/source identity and saved prediction fixture, and predicts validation/test batches without fitting or mutating inputs. Both predictors score identical rows. The constant baseline is the frozen training mean, checked against original training counts; `train.jsonl` is never reopened. The shared split reader validates consumed hashes, counts, binary labels, chronological keys and distinct identities across the evaluation splits. Existing outputs are refused, and failed runs cannot publish a complete report. Empty cohorts are rejected explicitly. Serving activation remains ticket 22.

JSON and Markdown record primary log loss, ROC-AUC, binary Brier loss, counts/clicks/observed CTR, full source/model settings, chronological boundaries and reliability bins. Single-class evaluation returns AUC null with a reason; explicit binary log-loss labels and Brier loss remain meaningful. Equal-width bins default to 20, fixed before evaluation; empty bins retain zero count/null means. PNG diagrams include per-bin counts, a populated-range calibration panel and a nonnegative symlog count panel. Both final diagrams were visually inspected; titles, axes, labels and synthetic limitations are visible. Tests also verify Markdown table continuity before the plots.

Reports distinguish probability scoring, discrimination and calibration. Lower log loss alone does not prove better calibration. There is no mandatory lift/score, and unfavorable outcomes remain reportable. Final-test outcomes did not change the generator, selected C, preprocessing or model; only report formatting/plot layout changed after initial inspection. No calibration fitting or live ingestion was introduced.

### Full retained-data evidence

[Report](../evidence/ticket21/report.md), [complete JSON](../evidence/ticket21/report.json), [repeat/audit measurement](../evidence/ticket21/full-measurement.json), [validation reliability](../evidence/ticket21/reliability-validation.png), [test reliability](../evidence/ticket21/reliability-test.png).

Frozen model `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`, pipeline SHA-256 `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`, C=0.1. Source is ticket 19's million-impression feature dataset, history `2ed92061-8b66-59b4-8a1b-509f340d47d0`, entity dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`. Training base rate is **15,606 / 700,000 = 0.022294285714285714**. Both evaluation cohorts have 150,000 impressions: validation has 3,408 clicks; final test has 3,337 clicks.

| Split | Predictor | Log loss | ROC-AUC | Brier loss |
| --- | --- | ---: | ---: | ---: |
| Validation | Frozen model | 0.10542357 | 0.63866634 | 0.02204824 |
| Validation | Training base rate | 0.10844812 | 0.50000000 | 0.02220398 |
| Final test | Frozen model | 0.10417316 | 0.62593177 | 0.02162058 |
| Final test | Training base rate | 0.10665850 | 0.50000000 | 0.02175175 |

Both final-code CLI runs produced identical complete reports and PNG checksums. The audit confirmed every bin count sums to its cohort count, both predictors preserve counts/clicks, and **every feature/model input file checksum remains unchanged**. Native CPython 3.10.11 wall costs were **12.661s / 14.715s** including startup, source validation, parsing, prediction, scoring, plotting and writing; concurrent checks ran. These are local offline demonstration costs, not controlled inference or serving benchmarks. Metrics describe this designed synthetic world's later outcomes, not real-user effectiveness or generalization to entirely unseen users/ads. The final-test model's highest populated bin has only 57 examples; calibration precision is limited there.

Memory scales with consumed rows and encoded features; each split is evaluated as one in-memory batch. Reliability calculations scan the rows per bin, O(rows*bins), with bins bounded 1–100. Native/container matching dependencies are pinned; runtime compatibility is validated before artifact loading. Lock resolution is 65 packages. Matplotlib has headless Agg rendering; Docker smoke sets a writable temporary Matplotlib config directory.

### Verification commands

From repository root unless noted. The initial dependency fetch in the sandbox failed DNS resolution; retry with authorized network access succeeded. Initial TDD report fixture omitted a required category_preferences field; the fixture was corrected. Visual QA found crowded plot labels and a clipped title; final populated-range/tight-layout figures were re-rendered and inspected. No underlying generator/model changes were made.

```powershell
# From backend/:
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock
..\.venv\Scripts\uv.exe sync --locked --python .venv/Scripts/python.exe
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ctr_evaluation.py -q
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket21_test'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m alembic -x database=test check
.\.venv\Scripts\python.exe -m hatchling build
..\.venv\Scripts\uv.exe lock --check --offline
# From repository root:
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket21-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket21_test
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket21/evaluate-and-audit.py artifacts/ctr-ticket19-full/first artifacts/ctr-ticket20-full/first artifacts/ctr-ticket21-verified
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket21/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket21/native-smoke.json
docker compose build backend
docker run --rm --env PYTHONPATH=/app --env MPLCONFIGDIR=/tmp/matplotlib --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket21,target=/evidence,readonly' adflow-backend:phase1 python /evidence/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket21/docker-smoke.json
Copy-Item artifacts/ctr-ticket21-verified/measurement.json .scratch/adflow-implementation/evidence/ticket21/full-measurement.json
Copy-Item artifacts/ctr-ticket21-verified/first/report.json .scratch/adflow-implementation/evidence/ticket21/report.json
Copy-Item artifacts/ctr-ticket21-verified/first/report.md .scratch/adflow-implementation/evidence/ticket21/report.md
Copy-Item artifacts/ctr-ticket21-verified/first/reliability-validation.png .scratch/adflow-implementation/evidence/ticket21/reliability-validation.png
Copy-Item artifacts/ctr-ticket21-verified/first/reliability-test.png .scratch/adflow-implementation/evidence/ticket21/reliability-test.png
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket21
backend/.venv/Scripts/python.exe -m ruff format --check .scratch/adflow-implementation/evidence/ticket21
git diff --check
```

Full regression: **519 passed in 151.81s**, including PostgreSQL integration tests in isolated adflow_ticket21_test. Strict mypy **87 source files clean**; Ruff lint/format pass; Alembic **no new upgrade operations**; sdist/wheel build pass; offline lock validation **65 packages**. Final plot-only adjustment is verified by refreshed focused tests, full-data repeat/audit and native/Docker smoke, without repeating unrelated regression.

### Standards

Independent read-only code-review agent: **0 documented violations, 0 heuristic findings**. Reusing the training module's feature-manifest/split reader avoids divergent validation; no actionable module/maintenance concerns were found.

### Spec

Independent read-only code-review agent: **0 actionable findings**. Frozen evaluation, training-only baseline, identical-row comparison, single-class limits, provenance and synthetic limitations match ticket 21 and the authoritative CTR/synthetic contracts. No scope creep or incorrect behavior was found. Serving activation remains deferred.

Review total: Standards 0; Spec 0; neither axis has an outstanding issue. Reviews used task-start HEAD plus the complete implementation's untracked files; final evidence/plot-layout verification was completed afterward by the parent agent.

Final focused evaluation suite: **22 passed in 35.48s** after the last plot-only adjustment. Refreshed native/Docker smoke reports both pass, reproduce complete outputs within their runtimes, and preserve all inputs. Final Docker image: `sha256:b4e7b5b5ec77b773f68783a1ce63e631b7fc8ea52c96d451ab663d98354fddec`, Python 3.12.15; native Python 3.10.11. Cross-runtime artifact equality is not claimed. Saved PNG SHA-256 hashes match the committed report manifest. Local PostgreSQL stopped cleanly after verification, retaining all databases/artifacts. All acceptance criteria pass.

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -w
git diff --cached --check
```

Final independent review of the evidence and plot-layout additions confirmed **Standards: 0 documented violations/0 actionable smells; Spec: 0 actionable findings**. Ticket comments match retained metrics, model identity, counts and native/Docker smoke records. Ticket 21 is complete.
