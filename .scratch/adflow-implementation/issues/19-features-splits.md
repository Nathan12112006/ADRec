# 19 — Build shared CTR features and chronological splits

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 17, 18

## Scope

Implement the five accepted features from immutable historical snapshots and the same builder for serving. Produce deterministic 70/15/15 chronological impression splits with label grouping and boundaries. Exclude IDs/bid/variant/hidden probabilities, activity and historical aggregate features.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [18 — Generate independent historical exposure and click outcomes](18-synthetic-history.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests cover overlap/category-match, empty interests, missing/unknown categoricals and snapshot stability.
- [x] Every impression/label belongs to exactly one temporal split; no future/outcome feature leakage.
- [x] Feature schema/version and source provenance are explicit.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and checks — 2026-10-08

Task-start baseline: `8141b3a1a4987ec31e551570ab61167426221b87`, clean current branch. Dependencies 17 and 18 were done. Nathan confirmed the shared public feature builder and offline history-to-feature/split writer as the TDD seams. No ADR directory exists. No dependencies or migrations changed.

Added `backend/app/ctr/features.py` with `ctr-features-v1` and exactly five allowlisted raw features, shared for historical preparation and later serving. Distinct interest overlap and category membership use user interests rather than hidden category preferences. Missing/null/empty categoricals use `__missing__`; unknown strings remain raw for training-only preprocessing in ticket 20. Excluded IDs, bids, variants, activity, generator fields, labels and aggregates never enter the feature object.

Added `backend/app/ctr/dataset.py` and explicit `python -m app.ctr.dataset --history PATH --output NEW_PATH`. It validates the complete versioned source manifest, all source hashes/counts, snapshot/exposure identities, references, binary labels, timezones and click consistency. A temporary SQLite database sorts by UTC impression time and integer ID, then streams deterministic 70/15/15 JSONL splits using floor boundaries. Labels stay with impressions regardless of click time. Snapshot catalogs use O(users+ads) memory; exposure memory is bounded with O(N) disk and O(N log N) sorting. The 8 MiB SQLite cache target is not a process memory cap. Manifests retain schema/version, split counts/clicks, first/last keys, row boundaries, file hashes, source manifest hash/history/dataset IDs and generator provenance. Existing output is preserved. Failed preparation cannot claim a complete manifest. README documents preparation, contracts, errors and costs.

TDD reds preceded the absent feature builder, absent split writer, duplicate-identity error translation, malformed manifest validation and absent CLI output. Windows cleanup initially failed because SQLite's transaction context leaves its connection open; explicit closing fixed it. A misplaced test assertion was corrected before final regression. Further checks cover empty/unseen categoricals, frozen snapshot stability, shuffle/time ties/timezone normalization, delayed clicks across boundaries, deterministic repeat output, small-dataset rounding/empty splits, checksum failures, invalid references/labels/times, excluded fields and existing-output preservation.

Focused tests: **27 passed in 5.32s**. Full native backend regression: **472 passed in 110.96s**, no skips, with a new isolated `adflow_ticket19_test` PostgreSQL database. Strict mypy: **82 source files passed**. Ruff lint and format: **82 files passed**. Hatchling wheel/sdist built. Docker Compose configuration and backend build passed; temporary Linux fixture reproduced 1,000 examples with 700/150/150 splits and identical repeat manifests; CLI preparation passed. The fixture uses no PostgreSQL and cannot modify live tables. No model quality or serving performance is claimed. Full-history evidence and independent review follow below before completion.

### Commands

From the repository root, local PostgreSQL and Git/Docker operations use sandbox escalation:

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket19-server.log -w
.local-postgres/pgsql/bin/psql.exe -h 127.0.0.1 -U adflow -d postgres -Atc "SELECT datname FROM pg_database WHERE datname='adflow_ticket19_test'"
# No existing database found:
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket19_test
docker compose config --quiet
docker compose build backend
Get-Content -Raw .scratch/adflow-implementation/evidence/ticket19/runtime-smoke.py | docker compose run --rm --no-deps -T backend python - > .scratch/adflow-implementation/evidence/ticket19/docker-smoke.json
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
```

From `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket19_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ctr_dataset.py tests/unit/test_ctr_features.py -q
.\.venv\Scripts\python.exe -m pytest --tb=short -q
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m hatchling build
```

Full retained history preparation/repeat/audit from the repository root:

```powershell
$env:PYTHONPATH='backend'
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket19/prepare-and-audit.py artifacts/history-ticket18-full/first artifacts/ctr-ticket19-full
backend/.venv/Scripts/python.exe -m ruff format .scratch/adflow-implementation/evidence/ticket19
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket19
git diff --check
```

The full preparation script times two sequential public-writer invocations, compares complete manifests and then audits every output against the original canonical-order history, checking unique ordered impression IDs, exact labels, feature allowlist and split hashes/counts. Timings include snapshot parsing/checksums and disk sorting/output; audits are excluded. A small Docker smoke ran during the first preparation, so these are local demonstration costs, not controlled performance comparison results. Raw feature outputs stay under ignored `artifacts/ctr-ticket19-full/`.

### Full-history evidence

Both preparations completed and their full manifests and output hashes match. Streaming audits of **all 1,000,000 impressions and 22,351 labels in each output** passed, with each impression/label in exactly one split and no fields outside the five-feature allowlist. [Full manifest](../evidence/ticket19/full-manifest.json) and [measurement/audit](../evidence/ticket19/full-measurement.json) record the actual identities, counts, boundaries, hashes and environment. Input is ticket 18's immutable history `2ed92061-8b66-59b4-8a1b-509f340d47d0`, dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`, generator `click-world-v1`, history seed 18/entity seed 180018.

| Split | Impressions | Positive labels | Inclusive impression IDs |
| --- | ---: | ---: | --- |
| Training | 700,000 | 15,606 | 0–699,999 |
| Validation | 150,000 | 3,408 | 700,000–849,999 |
| Final test | 150,000 | 3,337 | 850,000–999,999 |

First/repeat preparation wall costs were **51.042s / 53.669s**, Windows CPython 3.10.11. These include checksums, parsing, sort and writing, exclude subsequent audits and are not controlled performance evidence or model results. Full raw outputs are retained locally, not committed. Docker fixture passed on Python **3.12.15**, image `sha256:ecee84f999b4dc5790895696e277b433cacc749f0119183df2a28aac7f648532`. Native/container fixtures reproduce within each runtime; cross-runtime equality is not claimed. Alembic reports **no new upgrade operations** and offline lock validation resolves **48 packages**, unchanged.

Additional evidence/check commands, from repository root unless noted:

```powershell
Copy-Item -LiteralPath artifacts/ctr-ticket19-full/measurement.json -Destination .scratch/adflow-implementation/evidence/ticket19/full-measurement.json
Copy-Item -LiteralPath artifacts/ctr-ticket19-full/first/manifest.json -Destination .scratch/adflow-implementation/evidence/ticket19/full-manifest.json
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket19
backend/.venv/Scripts/python.exe -m ruff format --check .scratch/adflow-implementation/evidence/ticket19
# From backend/, with the same isolated test URL:
.\.venv\Scripts\python.exe -m alembic -x database=test check
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock --check --offline
```

Verification cleanup completed: native PostgreSQL stopped and the temporary Compose network removed, retaining all databases, volumes and artifacts. From repository root:

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -w
docker compose down
git diff --cached --check
```

### Independent review and commit status

The code-review skill ran separate parallel Standards and Spec agents against the complete staged diff from task-start `8141b3a1a4987ec31e551570ab61167426221b87`. **Standards: 0 actionable violations or baseline smells. Spec: 0 actionable findings**, including no missing requirements, incorrect behavior or scope creep. Reviews were read-only; no test/artifact runs were repeated. Final cleanup/review notes change documentation only.

All acceptance criteria and checks pass. Automatic approval review rejected committing directly to the current `main` branch, stating that explicit user authorization for that default-branch commit is required. Changes are staged and preserved; ticket remains active only pending that approval and the implement skill's required commit. No branch switch or indirect commit was attempted.

Nathan explicitly confirmed committing ticket 19 directly to `main`. All acceptance criteria, full regression, artifact audits and independent reviews pass; ticket 19 is complete.
