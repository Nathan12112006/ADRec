# 20 — Train a persisted preprocessing and Logistic Regression pipeline

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Reproducible command records parameters, class counts, dependency versions and split identity.
- [x] Insufficient labels/convergence problems are actionable; final test cannot influence selection.
- [x] The whole fitted pipeline is exportable for a shared serving path.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-08

Resumed the interrupted ticket 20 implementation from task-start commit `39fcedb`; ticket 21 remains dependent on this ticket. The earlier session confirmed the public training-command and exported-pipeline test seams and recorded red/green cycles. Added `app/ctr/training.py`, `app/ctr/inputs.py`, 25 focused tests, pinned runtime dependencies/lockfile, reproducibility scripts and README setup/behavior documentation.

The explicit offline command fits StandardScaler and unknown-tolerant OneHotEncoder with unweighted L2 Logistic Regression on training rows only. Validation log loss selects among C=0.1,1,10, with smallest C breaking exact ties; the chosen fitted pipeline is frozen and exported without refitting or opening the final-test file. Input hashes, chronological identities/boundaries, labels and counts are validated. Both training classes and convergence are required. Whole-pipeline export includes checksum, content identity, full split/source provenance, versions, parameters, training base rate, convergence and reload-checked predictions. Existing outputs are preserved; failures cannot publish a complete manifest.

Focused checks: **25 passed**; mypy **85 source files clean**; Ruff lint and formatting pass. Tests cover repeatability/reload, shared feature inputs, unseen/missing categories, validation-only changes leaving a fixed-C pipeline byte-identical, unread final-test content, malformed labels/features/identities, missing metadata, checksums, insufficient classes, actual convergence failure and CLI configuration/overwrite rejection.

Full retained-data evidence: [manifest](../evidence/ticket20/full-manifest.json), [timing/audit](../evidence/ticket20/full-measurement.json). Input is ticket 19's immutable feature dataset, history `2ed92061-8b66-59b4-8a1b-509f340d47d0`, entity dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`. Training used **700,000 rows / 15,606 clicks**; validation used **150,000 rows / 3,408 clicks**. Both public CLI runs produced identical full manifests and pipeline checksums. Selected C=0.1, validation log loss **0.10542356571960358**, 33 iterations; C=1 and10 also converged (38/20 iterations). This is a selection statistic, not final-test evidence or a guaranteed lift.

Model identity: `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`; pipeline SHA-256 `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`. First/repeat wall costs **25.323s / 18.567s**, Windows CPython 3.10.11, including startup/load/fit/export and excluding later audits. These are local offline costs, not controlled serving measurements. Final code was run again after the review cleanup and reproduced the same manifest/model identity.

[Native smoke](../evidence/ticket20/native-smoke.json) and [Docker smoke](../evidence/ticket20/docker-smoke.json) pass on Python **3.10.11 / 3.12.15**, respectively, verifying repeated training identity, reload and finite bounded probabilities for shared missing-feature input. Docker image: `sha256:a2f870c4764cd34038de91f8d33d7f9fe917c69d016d426a12214e052ec728bf`. Reproducibility is verified within each runtime; cross-runtime artifact equality is not claimed. Docker installs all pinned dependencies from the lockfile; native lock validation resolves **53 packages**, and source/wheel builds pass. Primary-source version/persistence documentation was rechecked; links are in README.

Memory grows with consumed rows/encoded features: raw arrays and identity validation are in memory; sparse categorical encoding reduces practical matrix storage. Candidates run sequentially and repeat preprocessing. There is no request-time model loading or training in this change; serving activation is ticket 22 and held-out evaluation is ticket 21.

Commands from repository root unless otherwise stated:

```powershell
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket20/train-and-audit.py artifacts/ctr-ticket19-full/first artifacts/ctr-ticket20-full
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket20/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket20/native-smoke.json
backend/.venv/Scripts/python.exe -m app.ctr.training --features artifacts/ctr-ticket19-full/first --output artifacts/ctr-ticket20-final
Copy-Item artifacts/ctr-ticket20-full/measurement.json .scratch/adflow-implementation/evidence/ticket20/full-measurement.json
Copy-Item artifacts/ctr-ticket20-full/first/manifest.json .scratch/adflow-implementation/evidence/ticket20/full-manifest.json
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket20
backend/.venv/Scripts/python.exe -m ruff format --check .scratch/adflow-implementation/evidence/ticket20
docker compose build backend
docker run --rm --env PYTHONPATH=/app --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket20,target=/evidence,readonly' adflow-backend:phase1 python /evidence/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket20/docker-smoke.json
# From backend/:
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ctr_training.py -q
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m hatchling build
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock --check --offline
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket20_test'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic -x database=test check
```

Verification setup corrections: the initial full suite omitted required `ADFLOW_DATABASE_URL` and reported 310 passes/187 fixture errors; rerun supplies both URLs. Initial Docker script invocation omitted `PYTHONPATH=/app`; the corrected command above passes. No implementation changes were needed for these environment errors. PostgreSQL recovered its existing local cluster after the earlier interrupted session; no databases or artifacts were deleted.

Independent code-review skill: parallel Standards and Spec reviews against task-start HEAD including untracked files. **Standards: 0 documented violations, 0 outstanding smell findings. Spec: 0 actionable findings.** The Standards reviewer suggested deriving preprocessing indices from named features; implemented and reviewer confirmed resolved. Final full-data identity remained unchanged after that cleanup.


Final regression: **497 passed in 91.49s**, including PostgreSQL integration tests using isolated adflow_ticket20_test; Alembic reports **no new upgrade operations**. All acceptance criteria pass. Final-test data fitting/evaluation remains deferred; only validation selection was performed.
