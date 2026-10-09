# 47 — Build controlled benchmark execution and provenance capture

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 45, 46

## Scope

Automate documented ramp, 60-second warm-up and 180-second measurement with finite drain. Support 10/100/500 users, three repetitions for quoted results, explicit cold reset/warm preparation and isolated database reset.

## Dependencies

- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [46 — Implement reproducible Locust benchmark workloads](46-locust-workloads.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Capture host/container resources, load-generator placement, one API worker, versions, seeds and artifact/configuration IDs.
- [x] Persist commands, raw exports, run boundaries, incomplete runs and drain limitations.
- [x] Protect retained demo history by using an explicitly isolated benchmark database and explicit reset command.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

2026-10-09 — Added a controlled runner, Locust phase controller, explicit benchmark
database reset command, and a Compose `benchmark` profile with a separate API service
that is configured for one Uvicorn worker and the isolated `adflow_benchmark` database.
The runner verifies the API container database name and confirms its newest dataset ID
matches the host profile connection before it starts. It rejects any other benchmark
database name. The reset utility also requires `--confirm-database adflow_benchmark`
and refuses the application database.

Each run saves its exact Locust command, pinned/runtime versions, git/source hashes,
dataset/API capability and CTR model identity, container image/resource limits and
mounts, host resources, container resource snapshots, phase timestamps, JSON outcome
summary, Locust CSV/HTML files, process log, exit status, and incomplete/drain state.
The controller waits for ramp completion, performs the 60-second warm-up, resets
Locust statistics at the measurement boundary, measures for 180 seconds, then stops
users with a finite 30-second task drain. Cold cache mode removes only keys for the
benchmark dataset after warm-up; warm mode keeps the profiles populated by warm-up.

Verification:

- `ruff check` and `ruff format --check` on benchmark scripts, phase controller, load workloads and lifecycle API files — passed; 10 files formatted.
- `python -m py_compile` on the benchmark runner, reset utility and Locust modules — passed.
- `python backend/scripts/benchmark_runner.py --help` and `python backend/scripts/reset_benchmark_database.py --help` — passed.
- `docker compose --profile benchmark config --services` — profile resolves; rendered `benchmark-api` command includes explicit `--workers 1`.
- Locust 2.46.7 live phase-controller smoke: one user, 1-second warm-up, 2-second measurement, 3-second drain. `phases.jsonl` recorded run start, ramp completion, warm-up completion, measurement start/end and drain start/completion. Locust measured 11 recommendation requests with zero failures; CSV and HTML exports were created. The whole-run semantic summary counted 16 completed recommendations including warm-up. This was a controller smoke against the local API, not a performance claim or the dedicated benchmark matrix.

The full 10/100/500 three-repetition matrix is ticket 49. The benchmark reset and
profile were documented and validated, but the dedicated benchmark database was not
reset or seeded while completing this runner ticket.
