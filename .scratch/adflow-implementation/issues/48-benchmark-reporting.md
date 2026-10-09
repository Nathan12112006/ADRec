# 48 — Produce honest latency and workload reports

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 30, 45, 47

## Scope

Report client HTTP, server and stage timings separately with mean/p50/p95/p99 by response population, opportunity/request throughput, CPU/memory, error categories and actual coverage.

## Dependencies

- [30 — Collect bounded rolling request and pipeline telemetry](30-rolling-telemetry.md)
- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [47 — Build controlled benchmark execution and provenance capture](47-benchmark-runner.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Never average percentiles across repetitions; preserve per-run results and explain any aggregation.
- [x] Disclose server histogram approximation and bounded telemetry drops/reset.
- [x] Reports distinguish durable selection work from lifecycle/event work, replay and no-ad traffic.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

2026-10-09 — Added `backend/scripts/report_benchmarks.py` and extended the Locust phase
controller to save workload-counter snapshots and AdFlow metrics snapshots immediately
around the measurement interval. The report shows client HTTP counts/latencies by
endpoint and response population, measured opportunity and event rates from cumulative
counter deltas, categorized errors, and host/API container resource snapshots. It retains
each repetition as its own row and never averages percentiles across runs.

Server request and stage percentiles are reported from the captured process-window
telemetry with sample count, coverage, process start, retention, and dropped count. They
are contextual rolling-window values, not run-isolated measurements; the two metrics
observer calls, warm-up, prior requests, and drain can appear in these snapshots. AdFlow
computes nearest-rank percentiles over its retained request samples. Locust client
percentiles use its response-time histogram approximation. Counter snapshots bracket
the measurement, so the report identifies tasks crossing a phase boundary and estimates
remaining in-flight opportunities. Resource reads are boundary snapshots, not peaks.

Verification:

- Ruff lint and format checks on the runner, report script, reset script, Locust workload/controller modules — passed (10 files already formatted).
- `python -m py_compile` on the benchmark runner, report/reset utilities, and Locust modules — passed.
- `python backend/scripts/report_benchmarks.py --help` — passed.
- A temporary, synthetic matrix smoke passed: the report parsed a Locust CSV row, derived a 21-completion counter delta, preserved server population/stage P95, and wrote both Markdown and JSON reports. The temporary matrix was removed automatically.
- `README.md` documents report generation, percentile methods, telemetry scope/drop/reset fields, and boundary limitations.
