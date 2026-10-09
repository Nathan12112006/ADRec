# 46 — Implement reproducible Locust benchmark workloads

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 32, 45

## Scope

Pin Locust and implement separate recommendation-only durable-write and full recommendation/impression/click workloads. Use reproducible uniform/hot users, unique opportunity keys and accepted semantic response classification.

## Dependencies

- [32 — Build reproducible API-driven demo traffic and edge scenarios](32-live-simulator.md)
- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Closed-loop load has no think time; user count is never labeled achieved RPS.
- [x] Transport, HTTP, timeout and semantic errors are counted distinctly.
- [x] Lifecycle requests honor impression-before-click; retries and replay populations remain identifiable.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

2026-10-09 — Implemented the two closed-loop workloads in `backend/loadtests/` and
pinned Locust 2.46.7 in the backend development group for Python 3.11+. Added the
recommendation response's `replayed` flag so clients can distinguish backend replay
from a new outcome. `README.md` documents both commands, profile choices, counters,
limits and official Locust references.

Verification:

- `backend/.venv/Scripts/ruff.exe check backend/loadtests backend/app/schemas/lifecycle.py backend/app/api/routes.py backend/tests/integration/test_http_lifecycle.py` — passed.
- `backend/.venv/Scripts/ruff.exe format --check backend/loadtests backend/app/schemas/lifecycle.py backend/app/api/routes.py backend/tests/integration/test_http_lifecycle.py` — 7 files already formatted.
- With `ADFLOW_RUN_POSTGRES_TESTS=1`, `ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow`, and `ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test`, `backend/.venv/Scripts/python.exe -m pytest backend/tests/integration/test_http_lifecycle.py -q` — 6 passed in 5.57s. The missing isolated `adflow_test` database was created; the retained `adflow` database and its volume were not reset.
- Locust 2.46.7 against the live Compose API, 1 user, seed 20261009, uniform profile selection, 5s: 15 opportunities started, 14 completed/selections, 1 in flight at stop; zero failed opportunities, HTTP/application/semantic errors, retries or backend-confirmed replays.
- Locust 2.46.7 against the live Compose API, 1 user, seed 20261009, hot subset of 5, 20s: 109 opportunities started, 108 completed/selections/impressions, 4 accepted clicks, 1 in flight at stop; zero failed opportunities, HTTP/application/semantic errors, retries or backend-confirmed replays. The separately emitted process-local replay population was empty and is explicitly not run-scoped.
- Both live runs used the configured dataset `07415efc-7c8f-5781-92d1-e922d81fa502` with a 100-user profile population. The backend container initially had an older API response; its two API source files were aligned to the workspace and the service restarted before these successful runs.

The bounded run duration can stop an opportunity while it is in flight; summaries report
that as `incomplete_opportunities` rather than counting it as completed. The test runs
were smoke checks and are not performance claims.
