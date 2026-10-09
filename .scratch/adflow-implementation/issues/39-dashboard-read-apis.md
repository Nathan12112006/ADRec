# 39 — Expose overview and performance summary APIs

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 30, 31, 38

## Scope

Implement read-only GET analytics/overview and GET metrics using durable business aggregates and bounded process-local telemetry. Reuse experiment result APIs; return summary data rather than raw event history.

## Dependencies

- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)
- [31 — Implement cohort-based experiment result aggregates](31-experiment-results.md)
- [38 — Verify and record the Redis phase gate](38-cache-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Overview covers the current dataset's live records; experiment summaries retain full cohorts.
- [x] Responses include as-of time, window, units, coverage and provisional/null states.
- [x] Tests reconcile totals with accepted events and distinguish missing telemetry from zero activity.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Added typed `GET /api/v1/analytics/overview` and `GET /api/v1/metrics` APIs. The overview chooses the latest dataset by creation timestamp (UUID tie-break), counts its current inventory and durable outcomes, scopes events through recommendations and request outcomes through users, and returns simulated revenue, observed CTR, a dataset-lifetime window, PostgreSQL snapshot coverage and 24-hour provisional status. No dataset returns an explicit successful empty state. Metrics returns the bounded 15-minute process telemetry with coverage/drop/sample data and units, process-lifetime cache counters, cache health and runtime capabilities. Experiment result APIs remain unchanged and preserve full experiment cohorts. README documents both API contracts and scope.

Verification from `backend/`, using the isolated PostgreSQL test database: `ADFLOW_RUN_POSTGRES_TESTS=1 python -m pytest tests/integration/test_dashboard_analytics.py tests/unit/test_http.py` — 32 passed. The overview integration scenario reconciles inventory, request outcomes/no-ad outcomes, recommendation, impression, click, exposed user, CTR and captured-bid revenue. Metrics test distinguishes no telemetry samples/null cache ratio from zero activity and checks coverage/window/capabilities. Ruff check/format and mypy passed (117 source files). The endpoint counts exclude offline historical artifacts. The default latest-dataset rule is now explicit in README; there is no separate dataset activation record.
