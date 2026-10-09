# Ticket 24 verification commands

From `C:\Project\AD Rec`, use the existing native locked CPython 3.10.11 environment.
PostgreSQL, TestClient and Docker verification ran outside the Windows sandbox.
All artifacts/databases remain retained; no development resets occur.

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket24-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket24_test
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket24/runtime-smoke.py artifacts/ctr-ticket23-reproduction/bundle | Set-Content .scratch/adflow-implementation/evidence/ticket24/native-smoke.json
docker compose config --quiet
docker compose build backend
docker run --rm --env PYTHONPATH=/app --env MPLCONFIGDIR=/tmp/matplotlib --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket24,target=/evidence,readonly' adflow-backend:phase1 python /evidence/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket24/docker-smoke.json
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
backend/.venv/Scripts/python -m ruff check .scratch/adflow-implementation/evidence/ticket24
backend/.venv/Scripts/python -m ruff format --check .scratch/adflow-implementation/evidence/ticket24
```

Docker CPython 3.12.15 explicitly builds a disposable 1,000-exposure history, feature
splits, trained/evaluated/packaged model inside its runtime before ranking. Native
smoke uses the retained full model. Both verify V1/V2 ordering on the same two ads,
zero-bid eligibility, stable JSON serialization, empty input and typed unavailability.
These are structural smoke checks, not a controlled latency or observed-lift study.
Docker image: `sha256:4bd58c90c029b7c3458ef5e3ec2e49e87a3a30859e42ab01104e4a7309b02223`.

From `backend/`:

```powershell
.venv/Scripts/python -m pytest tests/unit/test_ranking_strategies.py tests/unit/test_baseline.py tests/unit/test_ctr_serving.py -q
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket24_test'
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m mypy
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m alembic -x database=test check
.venv/Scripts/python -m hatchling build
$env:UV_CACHE_DIR='C:/Project/AD Rec/.uv-cache'
../.venv/Scripts/uv lock --check --offline
```

After verification, from repository root:

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -m fast
git diff --check
```
