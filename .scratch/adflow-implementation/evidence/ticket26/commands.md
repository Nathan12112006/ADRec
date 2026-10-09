# Ranking gate reproduction commands

Run from `C:\Project\AD Rec`, except the backend checks. PostgreSQL/TestClient and
Docker commands ran outside the Windows sandbox. Use only named isolated databases;
keep development/history/model artifacts. Existing native environment is CPython
3.10.11. No dependency update or retraining of the retained full model is involved.

```powershell
git rev-parse HEAD
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket26-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket26_test
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket26_examples
# From backend/:
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket26_test'
.venv/Scripts/python -m pytest tests/unit/test_ranking_strategies.py tests/unit/test_baseline.py tests/unit/test_ctr_serving.py tests/integration/test_ranked_recommendations.py tests/integration/test_recommendations.py tests/integration/test_events.py tests/integration/test_retrieval_serving.py tests/integration/test_http_lifecycle.py tests/integration/test_http_resilience.py tests/integration/test_ctr_availability.py -q
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m alembic -x database=test check
.venv/Scripts/python -m mypy
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m hatchling build
$env:UV_CACHE_DIR='C:/Project/AD Rec/.uv-cache'
../.venv/Scripts/uv lock --check --offline
```

The evidence scripts create output files exclusively; choose a new output path for
a rerun rather than deleting/replacing previous observations. Database seeding
appends an isolated namespace; it does not reset even the verification databases.
Prior artifact-generation/reload evidence remains in tickets 18–23.

```powershell
# From repository root:
$env:PYTHONPATH='backend'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket26/compare-strategies.py artifacts/history-ticket18-full/first artifacts/ctr-ticket23-reproduction/bundle .scratch/adflow-implementation/evidence/ticket26/comparison.json
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket26/measure-components.py artifacts/history-ticket18-full/first artifacts/ctr-ticket23-reproduction/bundle .scratch/adflow-implementation/evidence/ticket26/component-timings.json
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket26_examples'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket26_unused'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket26/response-examples.py artifacts/ctr-ticket23-reproduction/bundle .scratch/adflow-implementation/evidence/ticket26/response-examples.json
docker compose config --quiet
docker compose build backend
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
docker start adflow-ticket25-postgres
docker run --rm --network adflow-ticket25-verification --env PYTHONPATH=/app --env MPLCONFIGDIR=/tmp/matplotlib --env ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket25_test --env ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@adflow-ticket25-postgres:5432/adflow_ticket25_unused --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket25,target=/evidence,readonly' adflow-backend:phase1 python /evidence/http-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket26/docker-http-smoke.json
backend/.venv/Scripts/python -m ruff check .scratch/adflow-implementation/evidence/ticket26 .scratch/adflow-implementation/evidence/ticket25/http-smoke.py
backend/.venv/Scripts/python -m ruff format --check .scratch/adflow-implementation/evidence/ticket26 .scratch/adflow-implementation/evidence/ticket25/http-smoke.py
git diff --check
```

The Docker command reuses ticket 25's **isolated, unexposed** verification database,
not the development Compose service. It explicitly trains/evaluates/packages its
10,000-exposure fixture model before the actual server starts; no preparation is
added to application startup. After the initial readiness failure (connection refused; startup cause unknown), the shared
smoke was changed to 600 polling attempts at 0.1-second intervals with server-log
diagnostics; the exact Docker run command was repeated. Native examples initially
failed on an unsupported fixture retrieval topic; the corrected script uses cars.

```powershell
docker stop adflow-ticket25-postgres
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -m fast
```

Stop only services started for verification. No database, Docker container/network,
original artifact or durable history is removed. Image/model and actual check
outcomes are in [results](results.md) and linked JSON.
