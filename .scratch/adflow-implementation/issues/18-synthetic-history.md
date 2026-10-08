# 18 — Generate independent historical exposure and click outcomes

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 03, 17

## Scope

Build the versioned independent outcome generator and bounded-batch offline history CLI: randomized eligible exposure, interest/category/device signal, small hidden preferences and probabilistic clicks. Target configurable 1M impressions plus clicks for full data; preserve entity snapshots, streams, seeds and simulated times.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Same generator/configuration reproduces history with valid references and one complete binary label per impression.
- [x] Bid, experiment/model/ranking predictions never drive outcomes; hidden fields do not become model inputs.
- [x] Offline artifacts never write live event/experiment totals; observed synthetic-rate sanity checks and provenance are saved.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-08

Applied implement/TDD. Nathan explicitly confirmed the public outcome generator, offline history writer/CLI, PostgreSQL frozen source export and before/after live-table count seams. Task-start baseline: `df1747ef7251878b2d35780a889b8433c13abf88`; tickets 03 and 17 were done and the tree clean. No ADR directory exists. No new dependencies or database migrations were needed.

Added `backend/app/history/` with independent `click-world-v1` outcomes, `historical-exposure-v1` artifacts, read-only repeatable-read source export and explicit CLI; added the `adflow-history` console entry point. Source export captures all user fields and eligible ad fields (including advertiser identity/activity), then closes PostgreSQL before row generation. Source entities remain O(U+N) in memory; history uses O(B) row batches. Uniform randomized exposure, deterministic hidden entity offsets and per-opportunity outcome draws are independent of ranking, bids, models and experiments. Output includes one complete binary label and optional later click timestamp per exposure. Hidden offsets/probabilities are absent from saved training rows and source snapshots. Provenance snapshots retain bid but the outcome interface excludes it; upcoming ticket 19 owns allowed model-feature construction and split materialization.

Artifacts are separate JSONL files with a final complete manifest containing source/generator/runtime identity, configuration, hashes, synthetic-rate checks and simulated time/split definitions. Existing directories are refused. Filesystem failures retain failed status without claiming complete history. README documents exact preparation, formula/distributions, streams, files, scope, memory/time costs and limitations. Added repeatable measurement, streaming audit and Docker runtime smoke scripts under `../evidence/ticket18/`.

TDD reds: absent outcomes module before neutral/relevance probability implementation; absent sampling method before stable per-opportunity outcomes; absent artifact module before repeatable labeled files; absent export module before eligible frozen PostgreSQL snapshots; absent CLI before real subprocess generation/refusal; raw OverflowError before converting invalid simulated time ranges to configuration validation errors. Each behavior slice passed after implementation. Further same-seam checks cover bounded batching, delay/bid/outcome-setting independence, random nonmatching exposure, matched/unmatched rate sanity, source order, existing-file preservation, filesystem failure, invalid configuration, device/hidden signals, unknown/empty datasets, and no live-table writes. Initial Ruff import/format/line-length errors were corrected before final checks.

Focused history verification: **22 passed in 7.94s**. Final full native regression: **445 passed in 119.83s**, no skips. Strict mypy: **77 source files passed**. Ruff lint/format: **77 files passed**. Alembic: **no new upgrade operations detected**. Offline lock validation resolved **48 packages**, unchanged. Hatchling wheel/sdist passed; built wheel entry points contain `adflow-history`. Docker configuration/build passed; Linux Python 3.12.15 smoke reproduced 1,000 exposures/61 clicks and identical hashes/manifests through the public writer, and CLI help passed. Docker image: `sha256:97fb3e63061c6a7464e089581fed3bf5f7e7adea7d955708ee2a23f4aaf7698b`. Docker smoke uses a fixture and temporary files without PostgreSQL; actual PostgreSQL CLI/export integration is native Windows Python 3.10.11. Cross-runtime byte equality is not claimed.

Created separate `adflow_ticket18_test` and `adflow_ticket18_history` databases, preserving earlier databases. Full entity preparation completed with seed 180018 and dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`: **10,000 users, 100 advertisers, 100,000 ads**. Before history generation, recommendations/events/request outcomes were **0/0/0**. The one-million-exposure run and identical repeat are being measured sequentially after tests completed; final results and reconciliation follow below. Ticket remains active until evidence and review are complete.

### Exact commands and environment

From repository root, outside the sandbox for PostgreSQL/Docker and Git access:

```powershell
.local-postgres/pgsql/bin/pg_ctl.exe start -D .local-postgres/data -l .local-postgres/ticket18-server.log -w
.local-postgres/pgsql/bin/psql.exe -h 127.0.0.1 -U adflow -d postgres -Atc "SELECT datname FROM pg_database WHERE datname IN ('adflow_ticket18_test','adflow_ticket18_history')"
# Neither database existed; created both without touching earlier databases:
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket18_test
.local-postgres/pgsql/bin/createdb.exe -h 127.0.0.1 -U adflow adflow_ticket18_history
```

From `backend/`, final focused/regression/check invocations:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket18_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_history_outcomes.py tests/unit/test_history_artifacts.py tests/unit/test_history_cli.py tests/integration/test_history.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest --tb=short -q
.\.venv\Scripts\python.exe -m alembic -x database=test check
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
$env:UV_CACHE_DIR='C:\Project\AD Rec\.uv-cache'
..\.venv\Scripts\uv.exe lock --check --offline
.\.venv\Scripts\python.exe -m hatchling build
```

Full preparation and sequential CLI measurement from `backend/`, outside sandbox (full regression finished before measurement started):

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket18_history'
.\.venv\Scripts\python.exe -m alembic -x database=test upgrade head
.\.venv\Scripts\python.exe -m app.seeding.cli --database test --seed 180018 --users 10000 --advertisers 100 --ads 100000
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe ../.scratch/adflow-implementation/evidence/ticket18/measure-history.py --dataset-id b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c --output ../artifacts/history-ticket18-full --impressions 1000000
```

The measurement script invokes the real `app.history.cli.main` twice with seed 18, default batch size 1,000 and default time/outcome controls, using separate `first/` and `repeat/` outputs. Each timed wall/CPU interval includes PostgreSQL export and file generation but excludes entity seed preparation and subsequent memory reporting/audits. It compares complete manifests and records source hashes/runtime/hardware. Memory uses Windows process working set and cumulative peak after each run, including catalog/context allocations, not isolated history-batch memory. The repeat reuses the process. Code review during generation was read-only without test/large-audit workloads; these are local offline run costs, not throughput/capacity benchmarks.

Docker and saved evidence tooling from repository root:

```powershell
docker compose config --quiet
docker compose build backend
Get-Content -Raw .scratch/adflow-implementation/evidence/ticket18/runtime-smoke.py | docker compose run --rm --no-deps -T backend python - > .scratch/adflow-implementation/evidence/ticket18/docker-smoke.json
docker compose run --rm --no-deps -T backend python -m app.history.cli --help
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket18 --fix
backend/.venv/Scripts/python.exe -m ruff format .scratch/adflow-implementation/evidence/ticket18
git diff --check
```

Early integration slices used retained `adflow_ticket16_test` before dedicated ticket 18 databases existed; final focused/full checks used `adflow_ticket18_test`. All setup is explicit. No test database reset, live-history cleanup, automatic training or generation at startup occurred.

### Full history results and completion

Both runs completed successfully with **1,000,000 exposures and 22,351 clicks**, using dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c` and history seed 18. History identity: `2ed92061-8b66-59b4-8a1b-509f340d47d0`. Complete manifests and file hashes matched exactly. [Full manifest](../evidence/ticket18/full-manifest.json) and [measurement report](../evidence/ticket18/full-measurement.json) retain configuration, entity provenance, artifact/source hashes, synthetic rates, runtime/hardware and actual costs. Full source snapshots and histories remain locally under ignored `artifacts/history-ticket18-full/{first,repeat}/`, not large Git attachments.

| Run | Wall seconds | Process CPU seconds | Artifact bytes | Cumulative process peak working set bytes |
| --- | ---: | ---: | ---: | ---: |
| First | 119.880 | 116.047 | 195,766,408 | 371,613,696 |
| Repeat | 122.368 | 117.562 | 195,766,408 | 374,382,592 |

Windows CPython 3.10.11, AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD, 16 logical CPUs, colocated PostgreSQL 18.6. Memory after runs was 96,346,112 and 107,102,208 bytes, respectively. Timings include export/generation and exclude seed preparation; the repeat reuses the process. This is offline software cost, not HTTP latency or capacity. No universal duration or memory target is claimed.

Observed synthetic CTR: **2.2351%**. Matched-interest exposures: **332,551**, clicks **12,140**, rate **3.6506%**. Unmatched exposures: **667,449**, clicks **10,211**, rate **1.5299%**. Matching means at least one shared distinct interest. This sanity check confirms the intended aggregate tendency within the designed rules; it is not measured population behavior, model calibration, trained-model quality or ranking lift. No outcome parameters were changed after these observations.

Simulated impressions span 2026-01-01 00:00:00 UTC through 2026-01-12 13:46:39 UTC, one-second intervals, positive click delays 1–300 seconds. Manifest split boundaries are 700,000/850,000/1,000,000 by impression order; ticket 19 materializes the actual feature/split artifacts. The one-million target counts exposures; 22,351 positive labels carry their additional click outcomes/timestamps.

Streaming audits passed for **every row in both histories**: all three file hashes, exact ordered local impression IDs, valid user/ad references, active ad/advertiser flags, complete binary labels, exact simulated impression times and bounded subsequent click timestamps. No probabilities or hidden fields occur in row schemas. [First audit](../evidence/ticket18/first-audit.json), [repeat audit](../evidence/ticket18/repeat-audit.json). The initial enhanced auditor could not parse Pydantic's UTC `Z` on Python 3.10; normalizing that suffix in the auditor fixed it. Application generation was unchanged and no full generation rerun was needed. Evidence scripts passed final Ruff lint/format after correcting a formatting-only check on that auditor change.

Final database reconciliation matched the initial source: **10,000 users, 100 advertisers, 100,000 ads, 0 recommendations, 0 events, 0 request outcomes**. Both complete generation runs were read-only for PostgreSQL. No experiment subsystem exists yet and offline files cannot enter its live totals automatically.

Final evidence/reconciliation/cleanup commands from repository root:

```powershell
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket18/audit-history.py artifacts/history-ticket18-full/first > .scratch/adflow-implementation/evidence/ticket18/first-audit.json
backend/.venv/Scripts/python.exe .scratch/adflow-implementation/evidence/ticket18/audit-history.py artifacts/history-ticket18-full/repeat > .scratch/adflow-implementation/evidence/ticket18/repeat-audit.json
Copy-Item -LiteralPath artifacts/history-ticket18-full/measurement.json -Destination .scratch/adflow-implementation/evidence/ticket18/full-measurement.json
Copy-Item -LiteralPath artifacts/history-ticket18-full/first/manifest.json -Destination .scratch/adflow-implementation/evidence/ticket18/full-manifest.json
.local-postgres/pgsql/bin/psql.exe -h 127.0.0.1 -U adflow -d adflow_ticket18_history -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events), (SELECT count(*) FROM request_outcomes)"
.local-postgres/pgsql/bin/pg_ctl.exe stop -D .local-postgres/data -w
docker compose down
backend/.venv/Scripts/python.exe -m ruff format .scratch/adflow-implementation/evidence/ticket18
backend/.venv/Scripts/python.exe -m ruff check .scratch/adflow-implementation/evidence/ticket18
backend/.venv/Scripts/python.exe -m ruff format --check .scratch/adflow-implementation/evidence/ticket18
git diff --check
```

Native PostgreSQL stopped successfully and the temporary Docker network was removed. All databases, Docker volumes, source snapshots and history artifacts remain retained. No Compose PostgreSQL container was started for this ticket.

### Independent review

Implementation commit `7ee807e` reviewed with the code-review skill against task-start `df1747ef7251878b2d35780a889b8433c13abf88` via independent parallel Standards and Spec agents. Standards: **0 findings**; Spec: **0 findings**. Both inspected code/tests/docs and existing evidence without running tests or large audits during full-history measurement. The Spec reviewer required final million-exposure/repeat evidence, sanity rates and live-table reconciliation before marking done; those now pass as recorded above. Final evidence/documentation recheck is recorded below when returned. No application fixes were required by the code review.

Ticket 18 is complete and unblocks ticket 19. CTR feature building, split materialization, training/evaluation and live simulation remain later work.

Final independent recheck through `5cbfd3c`: **Standards 0 remaining findings; Spec 0 remaining findings**. Both reviewers confirmed that the completed measurement/audit outputs support the documented counts, hashes, synthetic rates, times and resource limits, and that all ticket acceptance criteria are met. No tests or large audits were repeated. Final note changes documentation only; application checks remain the passing 445-test/77-file results above.
