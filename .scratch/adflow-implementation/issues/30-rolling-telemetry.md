# 30 — Collect bounded rolling request and pipeline telemetry

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 07, 26, 29

## Scope

Implement the process-local telemetry needed before experiment results/dashboard: monotonic stage timings, 15-minute rolling retention with count/memory caps, experiment/variant diagnostics, request populations and reset/coverage/drop metadata. Keep durable business events authoritative.

## Dependencies

- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)
- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [29 — Route recommendations with immutable experiment attribution](29-experiment-routing.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests separate new selections, no-ad, replays, errors and event endpoints; no mean-of-percentiles aggregation.
- [x] Bounds, restarts, unknown attribution and missing telemetry are explicit rather than zero/perfect metrics.
- [x] Capture error/fallback populations even without a durable recommendation when possible; label incomplete outages.

## Comments

Added `RollingTelemetry`, a lock-protected process-local deque capped at 15 minutes, 10,000 records and approximately 8 MB. Both record retention and drop metadata are bounded. Dropped sample counts use one-second buckets, so even an oversized request cannot grow unbounded drop bookkeeping. Startup time, covered interval, sample/byte bounds, cap drops and incomplete-coverage status are exposed in the in-memory snapshot. A process restart starts a fresh interval; missing prior-process samples are not represented as zeros.

Middleware classifies new selections, no-ad outcomes, replays, impression events, click events, errors and other requests. Samples group by experiment, assigned variant, population and attribution state, with unresolved failures labeled `unknown`. Errors retain safe error codes. Request and per-stage averages and nearest-rank P50/P95/P99 are calculated from samples within each population; percentiles are never combined. Retrieval mode/fallback reason and stage sample counts are retained, including no-ad outcomes and errors occurring after retrieval. Event responses and telemetry derive experiment attribution from the saved recommendation. Durable PostgreSQL impression/click records remain authoritative. README documents population definitions, process restart, capacity and coverage limits.

Verification used isolated `adflow_ticket29d_test` on local PostgreSQL 18.6; the local server was stopped afterward and databases retained. From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/integration/test_ranked_recommendations.py backend/tests/integration/test_http_lifecycle.py backend/tests/integration/test_experiments.py backend/tests/unit/test_observability.py -q
backend/.venv/Scripts/python.exe -m mypy backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/ranking/strategies.py backend/tests/unit/test_observability.py backend/tests/integration/test_ranked_recommendations.py
backend/.venv/Scripts/python.exe -m ruff check backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/ranking/strategies.py backend/tests/unit/test_observability.py backend/tests/integration/test_ranked_recommendations.py
backend/.venv/Scripts/python.exe -m ruff format --check backend/app/core/observability.py backend/app/main.py backend/app/services/recommendations.py backend/app/services/events.py backend/app/api/routes.py backend/app/schemas/lifecycle.py backend/app/ranking/strategies.py backend/tests/unit/test_observability.py backend/tests/integration/test_ranked_recommendations.py
```

Results: 68 focused unit/PostgreSQL integration tests passed; mypy, Ruff lint and format passed. Bounds/eviction, stage percentiles and counts, startup coverage, oversize drops, new-selection/no-ad/replay/error/event populations, experiment/variant attribution, unresolved malformed-request attribution and retrieval fallback are covered. Telemetry remains process-local and volatile; no durable telemetry store or dashboard endpoint is claimed here.
