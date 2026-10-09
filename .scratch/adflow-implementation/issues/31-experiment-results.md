# 31 — Implement cohort-based experiment result aggregates

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 26, 29, 30

## Scope

Add results queries/API using recommendation creation cohorts and one as-of cutoff. Aggregate deduplicated exposed users/impressions/clicks/captured-bid revenue, recommendation/attempt/fallback/error diagnostics and separate latency populations; return null undefined ratios/lift.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [29 — Route recommendations with immutable experiment attribution](29-experiment-routing.md)
- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests reconcile counts/revenue with durable events and cover zero denominators/control, late events, stop/drain maturity and deduplication.
- [x] Provisional/synthetic/coverage/context labels are returned; failed reads are errors, not fabricated empty data.
- [x] No significance tests, winner declaration, selective fallback exclusion or raw-score comparison.

## Comments

Added `GET /api/v1/experiments/{id}/results` with optional timezone-aware `start_at` inclusive and `end_at` exclusive cohort bounds. It captures one server as-of time and executes all durable reads in one repeatable-read transaction. Recommendation creation determines the cohort; accepted impression/click events are joined through that recommendation and included only through the as-of cutoff, even if event arrival is later than the cohort end. Counts reconcile durable recommendations, request outcomes and deduplicated event rows. Ratios are null when their denominator is zero; relative lift is null if the control is zero/unavailable. Results separate process-local selection, no-ad, replay and error latency populations, report fallback counts without excluding them, and label telemetry coverage, synthetic status, cohort, as-of, 24-hour maturity and provisional state. Running experiments remain provisional; stopped experiments remain provisional while any included recommendation event window remains open. Database errors continue through the safe 503 handler. No significance test, winner declaration or raw-score comparison is added.

Verification used isolated `adflow_ticket29d_test` on local PostgreSQL 18.6; records were retained and the server was stopped after testing. From the repository root, with `ADFLOW_RUN_POSTGRES_TESTS=1`, `ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow`, and `ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket29d_test`:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/integration/test_ranked_recommendations.py backend/tests/integration/test_http_lifecycle.py backend/tests/integration/test_experiments.py backend/tests/integration/test_experiment_results.py backend/tests/unit/test_observability.py -q
backend/.venv/Scripts/python.exe -m mypy backend/app/experiments/results.py backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/schemas/experiments.py backend/app/ranking/strategies.py backend/tests/integration/test_experiment_results.py backend/tests/unit/test_observability.py
backend/.venv/Scripts/python.exe -m ruff check backend/app/experiments/results.py backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/schemas/experiments.py backend/app/ranking/strategies.py backend/tests/integration/test_experiment_results.py backend/tests/integration/test_ranked_recommendations.py backend/tests/unit/test_observability.py
backend/.venv/Scripts/python.exe -m ruff format --check backend/app/experiments/results.py backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/schemas/experiments.py backend/app/ranking/strategies.py backend/tests/integration/test_experiment_results.py backend/tests/integration/test_ranked_recommendations.py backend/tests/unit/test_observability.py
```

Results: 70 unit/PostgreSQL integration tests passed; mypy, Ruff lint and formatting passed. Tests reconcile captured-bid revenue and counts, exercise post-cohort late events on both sides of the as-of boundary, deduplicate event retries, verify zero-control null lift, include exact fallback, and check both running and stopped/drained maturity. The response reports incomplete process-local telemetry rather than implying a complete failure or latency census. README documents query bounds and metric definitions.
