# 51 — Verify and record the performance evidence phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 45, 50

## Scope

Audit benchmark provenance, correctness, quality and reproducibility, and summarize measured conclusions and limitations.

## Dependencies

- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [50 — Profile measured bottlenecks and verify justified improvements](50-profile-measured-bottlenecks.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] No comparative performance lift is quoted; measured claims link to their completed evidence.
- [x] Unachieved concurrency, approximate metrics and observed resource symptoms are explicit.
- [x] Offer checkpoint 62 and unlock Phase 9 after this technical verification.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Claimed by Codex on 2026-10-09 after dependencies 45 and 50 were done.

## Phase 8 performance gate

**Provenance:** the 24 paired smoke configurations each retain a matrix manifest, container/API settings, source hashes, dataset/model/ranking identity, identical starting table counts, per-run commands, phase timestamps, Locust exports/logs, counters, API snapshots, resource snapshots and generated reports under `artifacts/benchmarks/ticket49-paired-10/`. All used dataset `458a3900-0e21-57cc-88ca-877c7999f95d`, 1,000 users and 1,000 ads, `interest-overlap`, no CTR model, and one Uvicorn worker. All 24 short 10-user runs completed with no request errors. The paired workload comparison is a smoke check only: one repetition, 1-second warm-up, 3-second measurement and 3-second drain.

**Requested concurrency:** the separate 72-run diagnostics attempted 10/100/500 users for all retrieval/cache/workload/access combinations. 10-user attempts completed without errors. The 100/500-user runs exposed saturation and thousands of timeouts; the API container reached about 110% CPU during a 500-user attempt, the metrics observer timed out, and no selections completed in that 500-user measurement. These runs used a 100-user-per-second rapid ramp and their benchmark table counts accumulated between configurations. They remain saturation diagnostics and do not support comparative claims or a capacity limit. No 500-user success is claimed.

**Metric limits:** Locust's CSV latency percentiles are approximations from its response-time histogram, not exact per-request P50/P95/P99. Backend percentiles use a bounded process-local rolling sample and can include prior requests, observer calls and drain. The paired 10-user reports record the reset measurement window and counter deltas; their one short repetition is insufficient for a quoted performance comparison. Container snapshots do not expose a reliable physical CPU count; Docker showed no configured API CPU or memory quota. The host has 16 logical CPUs and 16 GB RAM, but the short diagnostics do not establish a stable host or service ceiling.

**Retrieval quality:** ticket 16 used a real 100,000-ad dataset and three repetitions per path. Flat full-retrieval P95 was 40.715 ms. The HNSW path including fallback P95 was 6,631.704 ms; mean tie-aware recall was 86.667%, minimum 0%, and 9/90 personalized samples used exact fallback. The quality/latency/fallback gate failed, so Flat remains the serving default. Ticket 16 retains the dataset identity, raw artifacts and checksums; this is component evidence and is not presented as an HTTP load result.

**Cache evidence:** ticket 37 reports one-run component profile-row query reductions for uniform/hot traffic, with explicit 50-user locality and no whole-service speedup claim. Ticket 49 now adds paired clean-state HTTP smoke coverage, but no cache or retrieval winner is claimed.

No hardware-independent latency, throughput, speedup or capacity promise is made. Phase 8 technical verification is complete and Phase 9 is unlocked. Ticket 62 remains a separate human checkpoint; no learning is claimed complete here.

Phase 8 gate closed on 2026-10-09 after the evidence and limitations above were audited. Human checkpoint 62 remains open and was offered separately.
