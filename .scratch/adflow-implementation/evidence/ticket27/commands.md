# Experiment schema and assignment checks

Run from `C:\Project\AD Rec`, except backend checks. PostgreSQL/Docker verification
ran outside the Windows sandbox. Only isolated databases are created; none are reset.

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket27-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket27_test
# From backend/:
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket27_test'
.venv/Scripts/python -m pytest tests/unit/test_experiment_assignment.py tests/integration/test_experiments.py tests/integration/test_persistence.py -q
.venv/Scripts/python -m mypy
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m alembic -x database=test check
.venv/Scripts/python -m hatchling build
$env:UV_CACHE_DIR='C:/Project/AD Rec/.uv-cache'
../.venv/Scripts/uv lock --check --offline
```

Red/green slices first observed missing assignment module and missing Experiment
record; focused checks passed after implementation. A strict type annotation for
the user-ID validator and SQL-string formatting were corrected before final checks.
Known digest vectors, exact threshold boundaries, fresh Python hash-seed processes,
default allocation, invalid inputs and changed experiment identity are tested at
the public assignment seam. Real PostgreSQL tests exercise draft edits, immutable
identity and started configuration, invalid raw writes, no resume/delete/truncate,
and simultaneous start transactions with one unique-index conflict. Integration
fixtures retain their rows and stop any experiment they start.

```powershell
# From repository root:
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket27_smoke
$env:PYTHONPATH='backend'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket27_smoke'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket27_unused'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket27/schema-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket27/native-smoke.json
docker compose config --quiet
docker compose build backend
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
docker start adflow-ticket25-postgres
docker exec adflow-ticket25-postgres pg_isready -U adflow
# Continue only after pg_isready succeeds:
docker exec adflow-ticket25-postgres createdb -U adflow adflow_ticket27_smoke
docker run --rm --network adflow-ticket25-verification --env PYTHONPATH=/app --env ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket27_smoke --env ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket27_unused --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket27,target=/evidence,readonly' adflow-backend:phase1 python /evidence/schema-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket27/docker-smoke.json
backend/.venv/Scripts/python -m ruff check .scratch/adflow-implementation/evidence/ticket27
backend/.venv/Scripts/python -m ruff format --check .scratch/adflow-implementation/evidence/ticket27
git diff --check
```

The smoke requires a fresh **isolated** `adflow_ticket27_smoke` database; on reruns
use a new isolated server/database arrangement rather than deleting retained data.
It explicitly migrates to0003, inserts durable dataset history, upgrades to0004,
checks unchanged old history and schema/metadata parity, saves assignment identity,
loads it in a fresh process, rejects a second running experiment and started edits,
and retains stopped history. Model ID is a valid-format fixture, not a loaded model;
activation availability and serving routing are later tickets. No application
startup preparation or HTTP/simulator experiment claim is introduced.

Docker uses the retained **unexposed** verification container/network with a new
database; no development Compose database is replaced. Its first setup attempt ran
createdb while PostgreSQL was still starting and failed before schema creation.
Checking readiness before createdb fixed setup, and the full smoke passed afterward.

```powershell
docker stop adflow-ticket25-postgres
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -m fast
```

Stop services started for verification, retaining every database, container/network,
original artifact and durable history. Actual results and image identity are in the
ticket comments and JSON reports.
