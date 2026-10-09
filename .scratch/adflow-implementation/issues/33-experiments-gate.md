# 33 — Verify and record the experimentation phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 26, 28, 31, 32

## Scope

Run assignment/lifecycle/concurrency/cohort/metric/failure regressions and the API simulator walkthrough. Save reconciled results with actual versions, errors and provisional status.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [28 — Expose validated experiment create/start/stop/list APIs](28-experiment-management.md)
- [31 — Implement cohort-based experiment result aggregates](31-experiment-results.md)
- [32 — Build reproducible API-driven demo traffic and edge scenarios](32-live-simulator.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Both variants appear with correct counts and stable treatment; no exact finite allocation or lift promise.
- [x] Start/stop/replay/late-click behavior and telemetry limitations are documented.
- [x] Offer the experiment learning checkpoint; unlock Phase 6 after this technical gate.

## Comments

Ran the walkthrough against isolated Docker PostgreSQL 18.6 databases `adflow_gate33_app` and `adflow_gate33_test`; applied migration `0005`. Docker Desktop 4.73.1 / Engine 29.4.3. The app database contains only a synthetic seed dataset (50 users, 10 advertisers, 200 ads; seed 330033, dataset `45db186a-f06e-5005-99fe-3a5c1904beb2`). The validated serving bundle was `artifacts/ctr-ticket23-reproduction/bundle`, model ID `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`.

Created and started experiment `ebc89825-6c1d-4187-bb3c-a2da4636f3a0` at 50/50 allocation, control `interest-overlap`, treatment `expected-value`, exact retrieval. Simulator run `1e07813c-f6b4-4c9f-90cc-8f242f27d10a`, seed 330033, requested 20 seconds at 5 opportunities/second: 100 attempts, achieved 5.0/sec, 100 selections, 100 accepted impressions, 7 accepted clicks, zero no-ad outcomes, retries or failures. Backend-derived allocation was control 65 / treatment 35; this demonstrates both variants without claiming exact finite allocation.

The results API reconciled control 65 recommendations / impressions, 5 clicks and simulated revenue `$23.0600`; treatment 35 recommendations / impressions, 3 clicks and `$14.5900`. After stopping, a replay of treatment request key `adflow/1e07813c-f6b4-4c9f-90cc-8f242f27d10a/0` returned the original recommendation `d012a46a-8d4d-4b66-9db4-5e827839b585` and treatment attribution. An accepted click after stop on that already-impressed recommendation retained treatment attribution and was counted once. The final results remain provisional because the 24-hour event window is open. Telemetry reports `coverage_complete: false`; all 100 recommendations used the visible exact fallback (`experiment_exact`). No significance test or winner declaration is made.

Verification after the gate walkthrough, using the isolated `adflow_gate33_test` database:

```powershell
$env:ADFLOW_DATABASE_URL = 'postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_gate33_app'
$env:ADFLOW_TEST_DATABASE_URL = 'postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_gate33_test'
$env:ADFLOW_RUN_POSTGRES_TESTS = '1'
backend/.venv/Scripts/python.exe -m pytest backend/tests/integration/test_ranked_recommendations.py backend/tests/integration/test_http_lifecycle.py backend/tests/integration/test_experiments.py backend/tests/integration/test_experiment_results.py backend/tests/unit/test_observability.py backend/tests/unit/test_simulator.py -q
backend/.venv/Scripts/python.exe -m mypy  # from backend/
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m ruff format --check backend
```

Results: 75 tests passed; mypy checked 109 source files successfully; Ruff passed and 109 files were formatted. Ticket 61, the experiment learning checkpoint, is ready for Nathan and remains a separate human task. The technical gate unlocks Phase 6.
