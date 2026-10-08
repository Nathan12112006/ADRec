# 07 — Expose lifecycle APIs with health checks and structured errors

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 01, 05, 06

## Scope

Add thin Pydantic/FastAPI routes for POST recommendations and impression/click events, GET /health/live and /health/ready. Enforce Idempotency-Key and input validation; standardize 200/204/404/409/410/422/503 responses. Add structured request/selection logging and stage timing hooks without a telemetry platform.

## Dependencies

- [01 — Create the backend package and configuration foundation](01-backend-foundation.md)
- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)
- [06 — Record client impressions and clicks with atomic accounting](06-event-workflow.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] TestClient verifies response schemas, empty 204 bodies, identifiers, validation and error mapping.
- [ ] Liveness survives DB loss; readiness reports it; responses never expose stack traces/credentials.
- [ ] Logs include request/selection context and durations; baseline probability remains absent/null.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
