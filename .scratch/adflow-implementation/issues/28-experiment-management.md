# 28 — Expose validated experiment create/start/stop/list APIs

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 26, 27

## Scope

Implement draft creation, start, stop and list APIs with draft->running->stopped transitions and no resume. Atomically reject concurrent/invalid starts or running-config edits; validate allocation, supported settings and pinned model availability.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [27 — Persist experiments and stable synthetic-user assignment](27-experiment-schema-assignment.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Test valid transitions, missing IDs, malformed config, second starts and model-unavailable activation.
- [x] Stopped records remain available; management APIs add no admin UI.
- [x] Document commands and preserve exact-retrieval fallback allowance.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. Implemented POST create/start/stop and GET list endpoints, strict configuration validation, pinned CTR model checks, draft-only activation and stop-only completion, and database-serialized transitions with the existing partial unique index as the concurrent-start arbiter. The API retains stopped records and does not add an admin UI. README now documents the commands and exact-retrieval fallback behavior.

Verification ran against fresh isolated database `adflow_ticket28_test` on the repository's local PostgreSQL 18.6 instance; existing databases were not reset. From `backend/`, with `ADFLOW_RUN_POSTGRES_TESTS=1`, `ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow`, and `ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket28_test`:

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_http_lifecycle.py tests/integration/test_experiments.py -q
.venv/Scripts/python.exe -m mypy app/api/routes.py app/ctr/serving.py app/experiments/management.py app/schemas/experiments.py
.venv/Scripts/python.exe -m ruff check app/api/routes.py app/ctr/serving.py app/experiments/management.py app/schemas/experiments.py tests/integration/test_http_lifecycle.py
.venv/Scripts/python.exe -m ruff format --check app/api/routes.py app/ctr/serving.py app/experiments/management.py app/schemas/experiments.py tests/integration/test_http_lifecycle.py
```

Results: 48 integration tests passed; mypy reported no issues; Ruff lint and format checks passed. Checks cover transitions, stopped record retention/listing, unknown IDs, malformed config, activation when the pinned model becomes unavailable, and conflict on a second active experiment. Model activation was exercised with a valid model-ID test double rather than deserializing a trained model artifact. PostgreSQL was stopped after the run and all database files remain retained.
