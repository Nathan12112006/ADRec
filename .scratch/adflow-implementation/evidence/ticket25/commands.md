# Ranked-selection verification commands

Run from `C:\Project\AD Rec` unless noted. PostgreSQL/TestClient/Docker commands ran
outside the Windows sandbox. Only explicitly isolated verification databases are
used; no development data resets occur. Existing native locked runtime is CPython
3.10.11; Docker runtime is CPython 3.12.15.

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket25-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket25_test
# From backend/:
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket25_test'
.venv/Scripts/python -m pytest tests/integration/test_ranked_recommendations.py tests/integration/test_recommendations.py tests/integration/test_retrieval_serving.py tests/unit/test_http.py -q
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m mypy
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m alembic -x database=test check
.venv/Scripts/python -m hatchling build
$env:UV_CACHE_DIR='C:/Project/AD Rec/.uv-cache'
../.venv/Scripts/uv lock --check --offline
```

The HTTP smoke launches the actual Uvicorn factory and uses standard-library HTTP
requests against its isolated database. It explicitly migrates/seeds before starting
the app; none of this preparation is application startup behavior. It verifies V2
selection/model provenance, immutable response replay after bid/deactivation edits,
impression/click/duplicate-click behavior, captured-bid credit, and JSON-safe logs.
Native smoke uses the retained full compatible model. The first native smoke passed
HTTP assertions but Windows cleanup briefly encountered an in-use server log; the
script now stops the spawned Windows test-server process tree before cleanup.

```powershell
# From repository root:
$env:PYTHONPATH='backend'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket25_test'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket25_unused'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket25/http-smoke.py artifacts/ctr-ticket23-reproduction/bundle | Set-Content .scratch/adflow-implementation/evidence/ticket25/native-http-smoke.json
docker compose config --quiet
docker compose build backend
docker network create adflow-ticket25-verification
docker run -d --name adflow-ticket25-postgres --network adflow-ticket25-verification --env POSTGRES_USER=adflow --env POSTGRES_PASSWORD=adflow --env POSTGRES_DB=adflow_ticket25_test postgres:18.6-bookworm@sha256:afc7e2d441324c0388fa80c3d24f733b4194a4eb7f47dd8ee2b08eb1a24a647c
docker run --rm --network adflow-ticket25-verification --env PYTHONPATH=/app --env MPLCONFIGDIR=/tmp/matplotlib --env ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket25_test --env ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket25_unused --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket25,target=/evidence,readonly' adflow-backend:phase1 python /evidence/http-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket25/docker-http-smoke.json
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
backend/.venv/Scripts/python -m ruff check .scratch/adflow-implementation/evidence/ticket25
backend/.venv/Scripts/python -m ruff format --check .scratch/adflow-implementation/evidence/ticket25
```

The Docker smoke explicitly prepares a disposable 10,000-exposure fitted/evaluated/
packaged model inside its own runtime. It uses a separate unexposed PostgreSQL
container, so native PostgreSQL can continue regression without port conflicts.
These are correctness checks, not observed-effectiveness or latency benchmarks.
Use a new container/network name or restart the retained verification container on
later reruns; no automatic database/container replacement is performed.

```powershell
docker stop adflow-ticket25-postgres
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -m fast
git diff --check
```

Stopping leaves verification databases, Docker data/container/network and original
artifacts retained. No application/Compose PostgreSQL service is replaced or reset.
