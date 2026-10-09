# 44 — Package and verify the complete read-only dashboard

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 38, 41, 42, 43

## Scope

Add frontend Docker/service configuration and document dashboard startup, API connectivity and demo walkthrough. Perform focused UI/build and API integration checks.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [41 — Build the live overview dashboard](41-overview-dashboard.md)
- [42 — Build experiment list and comparison detail views](42-experiment-dashboard.md)
- [43 — Build the rolling performance and dependency view](43-performance-dashboard.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Production frontend build succeeds and Compose exposes the documented application.
- [x] Verify polling failure recovery, paused/hidden states and responsive accessibility.
- [x] Use synthetic live traffic to reconcile dashboard values and save actual validation evidence.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implemented the production frontend runtime (`frontend/Dockerfile`, `frontend/server.mjs`) and Compose `dashboard` service bound to `127.0.0.1:5174`. It serves the production bundle as the unprivileged Node user, checks static-server health, proxies read-only GET API/health calls to the backend, and returns 405 for proxy write requests. Updated root and frontend setup instructions. The Node 24.14.1 base image is pinned to resolved digest `sha256:b506e7321f176aae77317f99d67a24b272c1f09f1d10f1761f2773447d8da26c`.

Checks completed: `npm run build` (pass; TypeScript and Vite production bundle), `npm run lint` (pass), `node --check frontend/server.mjs` (pass when run from the repository root), `docker compose config --quiet` (pass), production server smoke check (static app HTTP 200 and bundle referenced; `/health` HTTP 200; POST to `/api/v1/metrics` returns 405). Frontend build needs to run before Compose image packaging; documented `npm ci` and `npm run build` prerequisites. The dashboard remains unverified against the Compose backend and DB in its production container.

Blocking environment evidence: `docker compose build dashboard` failed during `npm ci` with Docker Desktop RPC EOF on two attempts. After that, `docker compose build dashboard` failed before build steps because Docker Desktop could not start its WSL engine (`DockerDesktop/Wsl/ExecError`, exit `0xc00000fd`). `docker desktop restart` followed by `docker desktop start` did not restore it; `docker desktop status` reports Desktop is not running. No volume removal/reset was attempted. `docker compose config --quiet` still parses successfully, but the Compose service cannot be built or exercised until Docker Desktop's WSL engine is restored. Ticket remains active because its Compose/live synthetic data acceptance checks are not complete.

Follow-up attempt: Docker WSL recovery succeeded once after `wsl.exe --shutdown` (the only listed distribution was `docker-desktop`, stopped); `docker compose build dashboard` then passed. Port 8000 was occupied, and port 8001 was also unavailable, so Compose now supports `ADFLOW_API_PORT`; starting with `ADFLOW_API_PORT=18000` brought PostgreSQL, Redis, backend and dashboard containers healthy. The retained `adflow` database was empty, so documented Alembic migrations and the idempotent small seed completed (dataset `07415efc-7c8f-5781-92d1-e922d81fa502`, 100 users, 20 advertisers, 1,000 ads). Dashboard static route/readiness passed, but API reads returned 404 because the prior backend image lacked current dashboard routes. `docker compose build backend` resolved and installed locked dependencies, then Docker Desktop again lost its daemon during image layer export (RPC EOF); subsequent WSL startup failed with the same `0xc00000fd`. No database or volume was removed. Remaining checks are to restore Docker Desktop, finish the backend image build, reconcile the dashboard against seeded durable data, send a small bounded synthetic traffic run, and verify browser polling/hidden/responsive behavior before closing ticket 44 and gate 45.

Current-state recheck (2026-10-08): Docker Desktop's CLI reports engine stopped; `wsl.exe --list --verbose` shows only `docker-desktop`, stopped. The latest `docker desktop start` says already running but engine remains stopped. A supported `docker desktop stop` / `start` cycle hung; launching the installed app directly did not start the WSL distro. The production frontend image and Compose exposure were successfully verified earlier in this turn (`docker compose build dashboard`; Compose dashboard status healthy at `127.0.0.1:5174`). The backend rebuild then lost the Docker daemon during export. Do not treat the earlier healthy state as proof the backend dashboard routes passed: the running backend image returned 404 for the analytics, metrics and experiment list routes. Ticket stays active pending rebuild and live integration.

Headless Edge UI verification (production bundle, `127.0.0.1:5175`; temporary mock API explicitly used): initial API failure showed the unavailable state; when the mock began serving overview JSON, the next poll recovered and rendered the data. After a successful response, stopping the mock and pressing Refresh retained prior data and displayed the stale warning. CDP network events recorded two overview requests before pause, no additional request over the next six seconds while paused, and an immediate request after Resume. To exercise the visibility listener, the page's `visibilityState` was overridden to `hidden` and a `visibilitychange` event dispatched; requests resumed when set to visible and stopped during the next six-second hidden interval. At a 375px device viewport, `scrollWidth` equaled `innerWidth` (375) with no horizontal overflow; inspected a screenshot. DOM checks found one main landmark, one h1, named links and buttons, and the stale status region. This verifies frontend recovery/visibility behavior against a mock and does not substitute for real backend/API data reconciliation.

Latest recovery audit (2026-10-08): `docker desktop status` still reports engine stopped; `wsl.exe --list --verbose` shows only `docker-desktop` and that distro is stopped. Retrying `docker desktop start` reported “already running” without starting WSL. A supported Desktop stop/start cycle hung, and launching the installed executable did not change WSL state. `docker desktop diagnose` did not return after repeated waits and was interrupted; no diagnostic bundle was uploaded. The unresolved blocker is host Docker Desktop/WSL recovery, not the frontend packaging or dashboard UI behavior.

Latest recovery audit (2026-10-08): Inspected the locally gathered Docker Desktop diagnostic bundle (`%LOCALAPPDATA%\Temp\adflow-docker-diagnostics.zip`, diagnostic ID `B4F03D44-7F9A-4E70-A5BF-907E2F708C55`; not uploaded). Docker backend logs show the WSL bootstrap starting against the existing data disk, then the backend monitor exits; diagnostic collection could not find Docker backend named pipes. The VM log records stale container layer unmount errors during teardown. A safe `wsl --shutdown` attempt from this session was denied with `Wsl/E_ACCESSDENIED`; consequently Desktop could not be cleanly restarted. `docker desktop status` says Docker Desktop is not running and `docker info` confirms the engine pipe is absent. No data or volumes were reset. The live integration acceptance remains blocked; the existing synthetic/mock UI verification does not satisfy it. Recovery needs an elevated WSL shutdown or Windows restart, then a fresh Docker engine check before continuing.

Current-state check (2026-10-09): `docker desktop status` cannot retrieve status, `docker info` returns permission denied for `npipe:////./pipe/dockerDesktopLinuxEngine`, and `wsl --list --verbose` returns `Wsl/E_ACCESSDENIED`. The named-pipe path now exists but is inaccessible from this session; this differs from the earlier missing-pipe check, but still provides no usable engine/API. `docker context ls` confirms `desktop-linux` is selected. No Docker process or Windows service state was exposed to this session. Ticket 44 remains active pending an accessible engine and live reconciliation.

Recovery retry (2026-10-09): `docker desktop start` returned without restoring CLI access. Immediate recheck: `docker desktop status` cannot retrieve status; `docker info` still reports permission denied on the selected `desktop-linux` engine pipe. Ticket 45 requires ticket 44 done and live checks against real API data; ticket 46 and subsequent Phase 8 tickets require gate 45 done. Per phase-order rules in the implementation spec, later tickets cannot be started while gate 45 is unmet. No further repo-side action can produce the missing live engine evidence in this session.

Live validation completed (2026-10-09): After the user opened Docker Desktop, a read-only check outside the restricted shell sandbox reached Docker Engine 29.4.3; `desktop-linux` had been inaccessible only from the sandbox. Restarted the existing Compose services with `ADFLOW_API_PORT=18000 docker compose up -d --wait`; backend, dashboard, PostgreSQL and Redis became healthy. Preserved all existing volumes. Found the app DB was at Alembic revision 0004 while the backend image expected 0005 (`request_outcomes.experiment_id` missing); inspected the additive migration `0005_experiment_attribution.py`, then applied `docker compose exec -T backend alembic upgrade head` (current revision 0005).

Ran bounded live traffic inside the backend container: `docker compose exec -T backend python -m app.simulator.cli --base-url http://127.0.0.1:8000 --duration-seconds 10 --rate-per-second 1 --seed 20261009 --max-retries 1`. Run `3c5dc98d-3b99-418a-9d07-b0324026b453` completed at 1.0 opportunity/s: 10 attempts, 10 selections, 10 accepted impressions, 0 accepted clicks, no failures or retries. The first pre-migration run correctly failed closed (10 `recommendation_unavailable` results); it produced no events and was followed by the migration before the successful run.

Compared live direct API JSON against the packaged dashboard's read-only proxy for `/api/v1/analytics/overview`, `/api/v1/metrics` and `/api/v1/experiments`: overview fields (dataset, availability/provisional status, users, advertisers, ads, recommendations, durable outcomes, exposed users, impressions and clicks) all matched; cache health and service capabilities matched; experiment arrays were empty in both paths. Durable dataset remains `07415efc-7c8f-5781-92d1-e922d81fa502` with 100 users, 20 advertisers and 1,000 ads; after traffic the overview reports 10 recommendations/outcomes, 10 impressions, 0 clicks and 9 exposed users. The visible production UI at `http://127.0.0.1:5174/` rendered those overview counts and provisional status; the Experiments view rendered its empty state; Performance rendered real rolling request/event populations, dependency health and cache counters. Existing mock-backed UI checks above cover unavailable recovery, stale data, paused/hidden polling and narrow viewport accessibility; these are distinct from this live API evidence. Performance telemetry includes the earlier expected failed pre-migration requests in its process-local error population. No public deployment or database reset was performed.
