# CTR gate reproduction commands

Run from `C:\Project\AD Rec` unless stated otherwise. Full artifacts are ignored and
retained in new directories; none of these commands reset development data. The
native runtime is the existing locked backend CPython 3.10.11 environment. Prepare
the source database/entities as documented in README when starting from scratch.

The canonical commands from `backend/`, with distinct application/test database
URLs configured, are:

```powershell
.venv/Scripts/python -m app.history.cli --database test --dataset-id $datasetId --output ../artifacts/history-new --impressions 1000000 --batch-size 1000 --seed 18
.venv/Scripts/python -m app.ctr.dataset --history ../artifacts/history-new --output ../artifacts/features-new
.venv/Scripts/python -m app.ctr.training --features ../artifacts/features-new --output ../artifacts/model-new
.venv/Scripts/python -m app.ctr.evaluation --features ../artifacts/features-new --model ../artifacts/model-new --output ../artifacts/evaluation-new
.venv/Scripts/python -m app.ctr.artifacts --model ../artifacts/model-new --evaluation ../artifacts/evaluation-new --output ../artifacts/bundle-new
.venv/Scripts/python -c "from pathlib import Path; from app.ctr.serving import CTRModel; m=CTRModel.load(Path('../artifacts/bundle-new')); print(m.predict_batch({'interests': []}, [{'id': 1, 'category': 'unseen'}]))"
```

For this gate, frozen source snapshots from ticket 18 are reused instead of exporting
the database again. The auditor calls the same `write_history` generator with the
original complete `HistoryConfig`, then invokes the public feature/train/evaluate/
package commands above. It requires exact equality with retained native artifacts
and checks original input hashes before/after. Use a new output path for each rerun.

```powershell
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket23/reproduce-gate.py artifacts artifacts/ctr-ticket23-reproduction .scratch/adflow-implementation/evidence/ticket23/reproduction.json
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket22/measure-inference.py artifacts/ctr-ticket23-reproduction/bundle artifacts/ctr-ticket23-reproduction/history .scratch/adflow-implementation/evidence/ticket23/inference-measurement.json
backend/.venv/Scripts/python .scratch/adflow-implementation/evidence/ticket22/runtime-smoke.py | Set-Content .scratch/adflow-implementation/evidence/ticket23/native-smoke.json
```

PostgreSQL verification uses an explicitly isolated database. The local server and
Docker commands require execution outside the Windows sandbox. Existing databases,
entity snapshots, history and model artifacts remain retained.

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket23-server.log -w
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket23_test
# From backend/:
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket23_test'
.venv/Scripts/python -m pytest tests/unit/test_history_outcomes.py tests/unit/test_history_artifacts.py tests/unit/test_history_cli.py tests/unit/test_ctr_features.py tests/unit/test_ctr_dataset.py tests/unit/test_ctr_training.py tests/unit/test_ctr_evaluation.py tests/unit/test_ctr_serving.py tests/integration/test_history.py tests/integration/test_ctr_availability.py -q
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m mypy
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m alembic -x database=test check
.venv/Scripts/python -m hatchling build
$env:UV_CACHE_DIR='C:/Project/AD Rec/.uv-cache'
../.venv/Scripts/uv lock --check --offline
```

Docker smoke prepares its own disposable small history/model inside CPython 3.12.15,
checks repeatability and resident predictions, then rejects the foreign native
bundle. It does not claim a full million-row Docker training benchmark or equal
native/container identities. The full native pipeline is measured separately.

```powershell
docker compose config --quiet
docker compose build backend
docker run --rm --env PYTHONPATH=/app --env MPLCONFIGDIR=/tmp/matplotlib --mount 'type=bind,source=C:\Project\AD Rec\.scratch\adflow-implementation\evidence\ticket22,target=/evidence,readonly' --mount 'type=bind,source=C:\Project\AD Rec\artifacts\ctr-ticket22-native,target=/native-bundle,readonly' adflow-backend:phase1 python /evidence/runtime-smoke.py /native-bundle | Set-Content .scratch/adflow-implementation/evidence/ticket23/docker-smoke.json
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
backend/.venv/Scripts/python -m ruff check .scratch/adflow-implementation/evidence/ticket23
backend/.venv/Scripts/python -m ruff format --check .scratch/adflow-implementation/evidence/ticket23
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -m fast
git diff --check
```
