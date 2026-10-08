# 01 — Create the backend package and configuration foundation

Status: ready-for-agent
State: active
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: none

## Scope

Create the approved backend package layout and FastAPI application factory with synchronous dependency seams. Configure environment-based application/test database URLs, log level and bounded connection settings; add .env.example, ignore rules, reproducible dependency configuration, pytest/TestClient and Python lint/type commands. Select compatible versions against primary sources at implementation time.

## Dependencies

No prerequisites. This is the first implementation ticket.

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] The app imports and configuration validation reports missing/invalid settings without leaking credentials.
- [ ] Application and test database settings are distinct; relevant setup/config checks and lint/type commands run.
- [ ] Document exact local install/run/check commands and the purpose of each module.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

