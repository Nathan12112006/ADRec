# 09 — Package the backend and document Phase 1 setup

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 03, 07

## Scope

Add backend Dockerfile and backend/PostgreSQL Compose operation, preserving local-backend development. Document explicit migration/seed preparation followed by ordinary startup, lifecycle curl/API walkthrough and test commands. Keep large history, model training and later services out of startup.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [07 — Expose lifecycle APIs with health checks and structured errors](07-http-health-logging.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Verify fresh-container and local-backend startup using the documented commands.
- [x] Document volumes/settings and isolated test setup; no silent data replacement or model/history generation.
- [x] README contains actual Phase 1 behavior and limitations, not future capability claims.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation evidence — 2026-10-07

Implemented by Codex using the implement skill. Added `backend/Dockerfile`, `backend/.dockerignore` and root `docker-compose.yml`; updated `.env.example` host URLs and README Docker/local preparation, lifecycle walkthrough, persistent volume/settings, isolated test setup, runtime differences and module boundaries. No application code, tests, dependencies or lockfile changed. Verified through the already agreed public HTTP/PostgreSQL seams rather than adding unit tests that mirror packaging configuration.

Packaging: a two-stage Dockerfile installs locked runtime wheels using uv `sync --locked --no-dev --no-install-project`, then copies the environment, application source and explicit Alembic migrations into the runtime image. Source imports from `/app`; the image seed command is `python -m app.seeding.cli`, avoiding an independently resolved build backend. UID/GID 10001 runs Uvicorn and the readiness health check. The allowlisted build context excludes host virtual environments, tests, caches, bytecode and dotenv files. Verified absence of pytest, uv, `/app/tests`, `/app/.env`, and host application bytecode in the runtime image. PostgreSQL health gates dependent startup. Only loopback ports 8000/5432 are published; container URLs use service DNS while host URLs use explicit IPv4. Credentials are the documented disposable demo values.

All base inputs are pinned by version/digest:

- Python 3.12.15 slim Bookworm: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`.
- uv 0.12.23: `sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21`.
- PostgreSQL 18.6 Bookworm: `sha256:afc7e2d441324c0388fa80c3d24f733b4194a4eb7f47dd8ee2b08eb1a24a647c`.
- Final backend image `adflow-backend:phase1`: `sha256:677b438e41d27c707fb70d7decf89efeb4816df6e2cea0fc5bbf174139e9dc40` (image export/provenance identity, not a performance claim).

Runtime: Docker engine 29.4.3, Compose 5.1.3, Linux amd64 containers on Windows Docker Desktop/WSL2. Local backend/tests use Windows CPython 3.10.11 and pytest 9.1.1; container runtime uses CPython 3.12.15 with the existing 23 locked runtime packages. ARM, other Python versions and public hosting were not exercised. Official uv Docker, Compose health ordering, Python/PostgreSQL image and libpq connection documentation were checked; relevant links are retained in README. Version-sensitive PostgreSQL 18 volume placement is `/var/lib/postgresql`, with PGDATA under its versioned child.

Used only dedicated Compose project `adflow-ticket09` and its newly created volume `adflow-ticket09_postgres_data`; earlier native databases on port 15432 were untouched. Docker Desktop was initially stopped; starting it in the background made the engine available without configuration/reset changes. Initial sandboxed WSL access failed; reviewed outside-sandbox Docker/TestClient/network execution succeeded, with no unresolved approval rejection.

Fresh verification first started both services with an empty volume. `SELECT to_regclass('public.datasets') IS NULL` returned true even after healthy API startup: startup performed no migration or seed. Then explicit migrations and default seeding produced 100 users, 20 advertisers, 1,000 ads, zero recommendations and zero events, with dataset `07415efc-7c8f-5781-92d1-e922d81fa502` (`entities-v1`, seed 42, Python 3.12.15). Repeating the identical seed reported `already_exists`. Container/local seed manifests differ by Python version, so README tells callers to reuse prepared entities or explicitly choose a separate dataset/project.

The documented HTTP walkthrough succeeded against the container API: recommendation `a851d7bd-e2e9-462f-a222-c84e31340833` for synthetic user `1171776452473855`, same-key replay with unchanged ID, null predicted CTR, click-before-impression 409, accepted impression/click and duplicate click 200. Direct event aggregation returned `click|1|4.9900` and `impression|1|0.0000`, matching the saved $4.99 bid. Liveness/readiness and OpenAPI checks passed.

Stopped only the Compose backend and ran local Uvicorn against Compose PostgreSQL, verifying health/OpenAPI and a second recommendation/impression/click with $4.99 credit (`82f8c30e-294f-4e5f-99ff-243c18487583`). The hidden local subprocess was stopped/waited in `finally`, and the container API restored. Ordinary `down` (without volume deletion) followed by `up -d --wait` preserved `100|20|1000|2|4` entity/recommendation/event counts. Local Uvicorn was also rechecked with corrected IPv4 example URLs and successfully replayed the first pre-restart recommendation without changing durable counts.

#### Connection diagnosis and correction

An initial full test run using `localhost` encountered wait assertions and was interrupted to narrow the repro. The existing `tests/integration/test_database_waits.py` deterministically reproduced two failures: a configured 3-second statement cancellation took 8.063 seconds (limit 8), and a 1-second lock wait took 6.063 seconds (limit 5). Ranked hypotheses were IPv6 fallback, Docker startup/resource pressure, and unapplied timeouts. DNS listed `::1` before `127.0.0.1`; the published Docker port was IPv4-only. A direct differential probe changed only the hostname and measured connection/query work at 5.077 seconds for `localhost` versus 0.054 seconds for `127.0.0.1`; both connections reported the same active statement/lock settings. This identified address fallback, not lost timeout configuration. Updated `.env.example` to IPv4 and documented the reason. No test threshold or database timeout was relaxed. The unchanged focused wait suite passed all four tests in 7.59 seconds, and the original full suite then passed. No temporary source instrumentation or new regression test was needed: the existing bounded-wait tests already caught the exact problem.

#### Commands and observed checks

All Compose commands ran from the repository root with `-p adflow-ticket09` to isolate verification. The README uses the default project for reviewer setup:

```powershell
docker compose -p adflow-ticket09 config --quiet
docker compose -p adflow-ticket09 build backend
docker compose -p adflow-ticket09 up -d --wait postgres
docker compose -p adflow-ticket09 run --rm backend python -m alembic upgrade head
docker compose -p adflow-ticket09 run --rm backend python -m app.seeding.cli
docker compose -p adflow-ticket09 up -d --wait
docker compose -p adflow-ticket09 ps
docker compose -p adflow-ticket09 run --rm backend python -m alembic check
docker compose -p adflow-ticket09 exec -T postgres createdb -U adflow adflow_test
docker compose -p adflow-ticket09 run --rm backend python -m alembic -x database=test upgrade head
docker compose -p adflow-ticket09 run --rm backend python -m alembic -x database=test check
docker compose -p adflow-ticket09 stop backend
docker compose -p adflow-ticket09 up -d --wait backend
docker compose -p adflow-ticket09 down
docker compose -p adflow-ticket09 up -d --wait
docker build --check backend
```

Executed the README PowerShell API requests (`Invoke-RestMethod` POST recommendations with a fresh Idempotency-Key, replay, impression, click and duplicate click; GET live/ready). Added explicit assertions for equal identities, null baseline probability, 409 ordering, captured decimal credit and database count/revenue aggregation. Queried seeded users from the active database rather than regenerating IDs with a different Python runtime. Local startup used `backend/.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` in a hidden subprocess, with a 30-second readiness deadline and guaranteed process cleanup. Ignored local logs are under `.uv-cache/ticket09-local.*.log`.

Final commands from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_database_waits.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Results: **186 passed in 30.16 seconds** (74 unit, 112 PostgreSQL integration). Strict mypy passed for 44 files; Ruff lint/format passed for 44 files. Application and test Alembic checks reported **No new upgrade operations detected**. Compose config validation and Docker build checks passed (**no warnings**). Post-suite application counts remained `100|20|1000|2|4`, so test execution did not mutate demo history. Repository-root `git diff --check` passed.

This ticket packages and verifies the Phase 1 demo. The Phase 1 completion gate is still ticket 10; later services, public hosting, performance claims and human learning certification remain outside this work.

#### Review and completion

Committed implementation as `3328589` (`Package Phase 1 Docker demo with explicit preparation and IPv4 host URLs`). Independent read-only Standards and Spec agents reviewed `git diff 25fbfe8f1381a3721c38795176b53f7eaa20685b...HEAD` against repository standards, the smell baseline, ticket 09 and governing Phase 1/delivery requirements. Standards: **0 findings**. Spec: **0 findings**. Reviewers inspected recorded verification without independently rerunning the suite; no corrective code changes were required.

After review, `docker compose -p adflow-ticket09 down` succeeded, removing both verification containers and their network while retaining `adflow-ticket09_postgres_data`. Docker Desktop remains available; no unrelated databases or containers were stopped. Completion evidence is committed separately from the reviewed implementation.
