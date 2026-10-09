# 54 — Run final correctness and build verification

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 9 — Final polish
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 51, 52, 53

## Scope

Run appropriate backend/integration/frontend builds and end-to-end demo regressions against final artifacts, including lifecycle races, failure paths and attribution.

## Dependencies

- [51 — Verify and record the performance evidence phase gate](51-performance-gate.md)
- [52 — Verify explicit artifact preparation and fresh Docker startup](52-fresh-setup-walkthrough.md)
- [53 — Finish reviewer documentation, diagrams and real screenshots](53-readme-reviewer-evidence.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Record exact checks, environment, artifact versions and failures/fixes.
- [x] Validate final migrations and documented fresh setup are reproducible.
- [x] Report remaining limitations without presenting unrun checks as passed.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Final regression — 2026-10-09

- Full backend suite: **678 passed in 170.45s**, with PostgreSQL integration enabled against isolated `adflow_test`. The first run exposed 14 stale assertions that compared entire idempotent retry responses, including the intentionally different `replayed` flag. Updated four integration test files to assert replay semantics and compare immutable payloads; all 57 affected tests passed, then the full suite passed.
- Static checks: Ruff lint passed; Ruff format check passed (128 files); strict `python -m mypy --no-incremental` passed (117 source files).
- Frontend: `npm run build` and `npm run lint` passed.
- Migration drift: `python -m alembic -x database=test check` reported `No new upgrade operations detected` against the isolated test DB. `docker compose config --quiet` passed.
- Docker images: `docker compose build backend dashboard` first encountered a Docker Hub 504 while fetching the frontend Dockerfile. Rebuilt backend and dashboard successfully with the legacy builder using the pinned/cached dependencies (`adflow-backend:phase1`, image `df549e80eef2`; `adflow-dashboard:phase7`, image `4d1bfd24ab7b`) and recreated only those services. PostgreSQL, Redis, backend and dashboard were healthy; backend readiness reported database/Redis ready and exact fallback; dashboard `/health` returned HTTP 200. The legacy builder emitted its deprecation warning.
- Fresh walkthrough evidence: ticket 52 records isolated database migration, artifact creation and an API/dashboard experiment flow. Ticket 53 contains actual dashboard screenshots. No existing database or volume was reset by this regression.

Limitations: Docker Hub's compose-build path failed with 504 and was bypassed by successful local image builds. The main demo has no CTR model configured. Performance smoke runs remain bounded diagnostics, not fixed-rate capacity evidence; human learning checkpoints remain open. No check is reported from the current shell after its Docker named pipe became unavailable on resume.