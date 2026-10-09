# 42 — Build experiment list and comparison detail views

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 38, 40

## Scope

Display experiment lifecycle, configuration and full-cohort V1/V2 metrics with exposed users, impressions, clicks, CTR, revenue, revenue per exposed user and relative lift.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [40 — Create the React dashboard shell and reliable polling](40-frontend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Show cohort cutoff/as-of/provisional status and null lift when control is zero.
- [x] Include relevant failure/replay/fallback diagnostics without excluding failed treatment attempts.
- [x] No browser management controls, significance, winner or rollout claims.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implemented the responsive, read-only experiment list and detail in `frontend/src/Experiments.tsx`, styled in `frontend/src/App.css`, using the existing experiment API types and polling hook. The view shows status/configuration, cohort start and exclusive cutoff, as-of time, provisional maturity, control/treatment outcomes, full comparison including lift, fallback counts, no-ad/replay/failure telemetry and coverage gaps. Missing/zero control values display null lift as an em dash. Unknown attribution errors remain explicitly unassigned. No significance test, winner, rollout language or management controls are present.

Verification (2026-10-08; API sample timestamps reflect the DB clock): `npm run build` (pass; TypeScript and Vite production build), `npm run lint` (pass, no diagnostics), GET `/api/v1/experiments` and selected GET `/api/v1/experiments/{id}/results` through Uvicorn on `127.0.0.1:8001` (pass; 1 experiment, 100 durable attempts split 65/35, 100 recommendations and impressions, 8 clicks, simulated revenue 23.0600/14.5900, cohort cutoff/as-of/provisional and fallback data present), Vite dashboard route HTTP 200 on `127.0.0.1:5173`. Data is synthetic and telemetry coverage was incomplete; this run confirms response shape and available render inputs, not statistical conclusions. An initial build ran out of Node memory under the default environment; rerun with `NODE_OPTIONS=--max-old-space-size=2048` succeeded. No browser screenshot was captured because the app preview transport was unavailable in this environment.
