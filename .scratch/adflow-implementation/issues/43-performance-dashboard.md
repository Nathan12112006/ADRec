# 43 — Build the rolling performance and dependency view

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 38, 40

## Scope

Display rolling 15-minute request/population latency, throughput, failures, cache counters and dependency capabilities using GET metrics.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [40 — Create the React dashboard shell and reliable polling](40-frontend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Disclose actual coverage, process reset/drop/cap limitations and nearest-rank sample percentile method.
- [x] Separate selected responses, replay, no-ad, failures and client events.
- [x] Do not present process-local metrics as distributed monitoring or cache hit share as overall request success.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implemented the polling performance/dependency view in `frontend/src/Performance.tsx`, typed metrics in `frontend/src/api.ts`, and responsive styling in `frontend/src/App.css`; the shell now mounts it for the Performance route. It reads `/api/v1/metrics` and `/health/ready`, separates response populations from impressions/clicks, reports throughput over covered elapsed seconds, displays per-population nearest-rank latency estimates and failure/fallback details, and surfaces capabilities, readiness and cache counters. Coverage window, process reset time, dropped samples, retained sample count, configured record/byte limits and current retained bytes are visible. Cache hit share is explicitly scoped to cache accesses/process lifetime.

Verification: `npm run build` (pass with `NODE_OPTIONS=--max-old-space-size=2048`), `npm run lint` (pass, no diagnostics), direct GETs to `/api/v1/metrics` and `/health/ready` (pass; partial window from process start, 4 retained samples, zero drops, PostgreSQL/Redis ready, exact fallback, V1 enabled, V2 disabled), same metrics through Vite proxy (pass), `/performance` SPA route (HTTP 200). Percentiles are nearest-rank estimates from the retained observations, not histogram buckets or guarantees. No browser screenshot captured; the app preview transport was unavailable.
