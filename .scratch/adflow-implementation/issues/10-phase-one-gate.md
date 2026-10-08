# 10 — Verify and record the Phase 1 completion gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 08, 09

## Scope

Run the complete canonical Phase 1 gate and record files/changes, actual checks, commands, limitations and next phase. Reconcile the documented recommendation/impression/click/replay walkthrough with durable counts. Offer the linked lifecycle learning checkpoint without answering for Nathan.

## Dependencies

- [08 — Verify lifecycle races, expiration and dependency failures](08-lifecycle-integration-tests.md)
- [09 — Package the backend and document Phase 1 setup](09-backend-docker-setup.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Migrations, seeding, lifecycle/unit/PostgreSQL checks and both startup modes pass or failures are fixed.
- [x] Evidence distinguishes implemented behavior from planned later phases.
- [x] Phase 2 remains blocked until this technical gate is done; human checkpoint stays separately tracked.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Phase 1 technical gate — 2026-10-07

Verified by Codex using the implement skill against application snapshot `9352dff7e8e9e46cc81e2c028dcea4a6df79542b` (the task-start review baseline). Dependencies 08 and 09 were already done. No application, migration, dependency or test behavior needed fixing. Added `../evidence/phase-one-gate.py`, a retained manual HTTP/PostgreSQL walkthrough and count reconciliation script; updated README with the actual completion boundary and ticket 57 with the offered human exercise. The script targets only the explicitly isolated `adflow-ticket10` project, requires untouched default-seeded data, creates two opportunities and retains their history. For another run, prepare a separate fresh database/project rather than deleting records from the retained volume. Its fixed $4.99 expectation comes from the documented default dataset's first user's selected bid, independently reconciled with API payloads and PostgreSQL aggregates.

Runtime/configuration: Windows CPython 3.10.11, pytest 9.1.1; Linux amd64 container CPython 3.12.15, PostgreSQL 18.6, Docker engine 29.4.3, Compose 5.1.3. Existing locked packages/base image digests are unchanged from ticket 09. Rebuilt backend image identity: `sha256:55363687813373308ff94c21d664a0fe5a9ef2860fb04662c1c2615b3288e22d`. Dedicated new volume: `adflow-ticket10_postgres_data`. Demo URL: `postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow`; separate test URL ends in `/adflow_test`. No native PostgreSQL or earlier ticket volume was used or reset.

#### Exact commands and results

From repository root (each Compose command uses the isolated project):

```powershell
docker compose -p adflow-ticket10 config --quiet
docker info --format '{{.ServerVersion}}'
docker compose ls
docker volume ls --filter name=adflow-ticket10
docker ps --format '{{.Names}} {{.Ports}}'
docker compose -p adflow-ticket10 build backend
docker compose -p adflow-ticket10 up -d --wait
docker compose -p adflow-ticket10 exec -T postgres psql -U adflow -d adflow -Atc "SELECT to_regclass('public.datasets') IS NULL"
docker compose -p adflow-ticket10 run --rm backend python -m alembic upgrade head
docker compose -p adflow-ticket10 run --rm backend python -m app.seeding.cli
docker compose -p adflow-ticket10 run --rm backend python -m app.seeding.cli
docker compose -p adflow-ticket10 exec -T postgres createdb -U adflow adflow_test
docker compose -p adflow-ticket10 run --rm backend python -m alembic -x database=test upgrade head
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/phase-one-gate.py
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
docker compose version --short
docker compose -p adflow-ticket10 run --rm backend python -m alembic current
docker compose -p adflow-ticket10 run --rm backend python -m alembic check
docker compose -p adflow-ticket10 run --rm backend python -m alembic -x database=test check
docker build --check backend
```

Initial Docker access inside the sandbox returned pipe permission denied. Reviewed outside-sandbox execution succeeded; no unresolved approval rejection remains. Inventory confirmed no existing ticket10 project/volume or running containers before preparation. Fresh healthy startup returned `t` for absent datasets table: it did not migrate/seed automatically. Explicit migration reached `0002 (head)`. Default seed created dataset `07415efc-7c8f-5781-92d1-e922d81fa502` (`entities-v1`, seed 42, Python 3.12.15) with `100|20|1000` entity counts and no request outcomes/recommendations/events. Identical repeat seed returned `already_exists`. Both application/test Alembic checks returned **No new upgrade operations detected**. Compose configuration passed; Docker build check completed with **no warnings**.

The retained script contains the exact HTTP requests, SQL, local Uvicorn command and subprocess cleanup used to run the README lifecycle in each startup mode. It also checks click-before-impression 409, equal full recommendation and event replays, null predicted CTR, live/ready/OpenAPI, actual database outage, local replay of a Docker-created selection, and container recreation without volume deletion.

| Mode | Recommendation | Request key | Confirmed events | Click credit |
| --- | --- | --- | --- | --- |
| Docker | `975a366d-6cf0-4ed2-8167-8efe58d1086c` | `48813509-0df4-4bc6-9001-c850b5dc3c90` | 1 impression, 1 click | $4.9900 |
| Local Uvicorn | `f305e5b3-8e6f-4dde-a608-5710e577371f` | `1d401b21-c933-424a-97a5-452b73852a24` | 1 impression, 1 click | $4.9900 |

Each selection/replay creates no impression by itself. Duplicate impressions/clicks retained identical responses and one event per type. PostgreSQL returned `click|1|4.9900` and `impression|1|0.0000` for each recommendation. Combined counts were `100|20|1000|2|2|4|9.9800` (users, advertisers, ads, request outcomes, recommendations, events, simulated revenue). These survived `down`/`up -d --wait` and replay. During stopped PostgreSQL, live returned 200, ready 503, recommendation 503; restoration recovered readiness without recording the failed opportunity.

From `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --tb=short
```

Strict mypy: **44 source files passed**. Ruff lint/format: **44 files passed**. Full regression: **186 passed in 29.68 seconds**, comprising 74 unit and 112 real PostgreSQL integration checks. This includes baseline ties/inactivity/zero bids/empty interests; concurrent recommendation/event retries; response loss; no-ad replay; mismatched keys/users; click ordering; exact expiration boundaries; changed bid/eligibility; unknown/malformed identities; connection/statement/lock/pool waits; durable insert/commit failures and rollback. Existing tests use Nathan's previously agreed public HTTP/PostgreSQL and persistence observation seams; no new application tests were necessary for this verification ticket.

Post-suite reconciliation and cleanup from root:

```powershell
docker compose -p adflow-ticket10 exec -T postgres psql -U adflow -d adflow -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM request_outcomes), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events), (SELECT sum(simulated_revenue) FROM events)"
docker compose -p adflow-ticket10 ps
docker compose -p adflow-ticket10 down
backend/.venv/Scripts/python.exe -m ruff check --fix .scratch/adflow-implementation/evidence/phase-one-gate.py
backend/.venv/Scripts/python.exe -m ruff format .scratch/adflow-implementation/evidence/phase-one-gate.py
backend/.venv/Scripts/python.exe -m ruff format --check .scratch/adflow-implementation/evidence/phase-one-gate.py
git diff --check
```

Demo counts remained **100|20|1000|2|2|4|9.9800**, proving isolated test execution did not mutate the demo history. Both services were healthy before shutdown. Containers/network were stopped/removed; volume and data retained. Local process was stopped/waited by `finally`; local logs remain ignored at `.uv-cache/ticket10-local.log`. The evidence script's initial import-order warning was fixed; formatting changed only whitespace/import order after execution.

#### Boundaries and next phase

Phase 1's canonical technical gate passes. Transaction uniqueness and atomic saved outcomes/event credits remain the correctness mechanism; saved snapshots preserve replay through later ad changes. README documents selection's expected O(U + N*A) overlap work, candidate materialization cost, bounded dependency waits and durable-history growth. These checks establish correctness and reproducible setup, not load capacity or a speedup. Other runtimes/architectures are unverified; no FAISS/model/experiment/Redis/frontend implementation or benchmark result is claimed.

Phase 2 was held until this gate passed. Ticket 11 (topic vectors/retrieval contract) is now technically unblocked and remains open; no Phase 2 implementation was started. Offered the linked ticket 57 lifecycle explain-and-modify exercise, recorded separately with `State: open`. Nathan has not supplied an explanation or directed a change; human learning is not certified by this gate.
