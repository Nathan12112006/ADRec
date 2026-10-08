# 18 — Generate independent historical exposure and click outcomes

Status: ready-for-agent
State: active
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

- [ ] Same generator/configuration reproduces history with valid references and one complete binary label per impression.
- [ ] Bid, experiment/model/ranking predictions never drive outcomes; hidden fields do not become model inputs.
- [ ] Offline artifacts never write live event/experiment totals; observed synthetic-rate sanity checks and provenance are saved.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-08

Applied implement/TDD. Nathan explicitly confirmed the public outcome generator, offline history writer/CLI, PostgreSQL frozen source export and before/after live-table count seams. Task-start baseline: `df1747ef7251878b2d35780a889b8433c13abf88`; tickets 03 and 17 were done and the tree clean. No ADR directory exists. No new dependencies or database migrations were needed.

Added `backend/app/history/` with independent `click-world-v1` outcomes, `historical-exposure-v1` artifacts, read-only repeatable-read source export and explicit CLI; added the `adflow-history` console entry point. Source export captures all user fields and eligible ad fields (including advertiser identity/activity), then closes PostgreSQL before row generation. Source entities remain O(U+N) in memory; history uses O(B) row batches. Uniform randomized exposure, deterministic hidden entity offsets and per-opportunity outcome draws are independent of ranking, bids, models and experiments. Output includes one complete binary label and optional later click timestamp per exposure. Hidden offsets/probabilities are absent from saved training rows and source snapshots. Provenance snapshots retain bid but the outcome interface excludes it; upcoming ticket 19 owns allowed model-feature construction and split materialization.

Artifacts are separate JSONL files with a final complete manifest containing source/generator/runtime identity, configuration, hashes, synthetic-rate checks and simulated time/split definitions. Existing directories are refused. Filesystem failures retain failed status without claiming complete history. README documents exact preparation, formula/distributions, streams, files, scope, memory/time costs and limitations. Added repeatable measurement, streaming audit and Docker runtime smoke scripts under `../evidence/ticket18/`.

TDD reds: absent outcomes module before neutral/relevance probability implementation; absent sampling method before stable per-opportunity outcomes; absent artifact module before repeatable labeled files; absent export module before eligible frozen PostgreSQL snapshots; absent CLI before real subprocess generation/refusal; raw OverflowError before converting invalid simulated time ranges to configuration validation errors. Each behavior slice passed after implementation. Further same-seam checks cover bounded batching, delay/bid/outcome-setting independence, random nonmatching exposure, matched/unmatched rate sanity, source order, existing-file preservation, filesystem failure, invalid configuration, device/hidden signals, unknown/empty datasets, and no live-table writes. Initial Ruff import/format/line-length errors were corrected before final checks.

Focused history verification: **22 passed in 7.94s**. Final full native regression: **445 passed in 119.83s**, no skips. Strict mypy: **77 source files passed**. Ruff lint/format: **77 files passed**. Alembic: **no new upgrade operations detected**. Offline lock validation resolved **48 packages**, unchanged. Hatchling wheel/sdist passed; built wheel entry points contain `adflow-history`. Docker configuration/build passed; Linux Python 3.12.15 smoke reproduced 1,000 exposures/61 clicks and identical hashes/manifests through the public writer, and CLI help passed. Docker image: `sha256:97fb3e63061c6a7464e089581fed3bf5f7e7adea7d955708ee2a23f4aaf7698b`. Docker smoke uses a fixture and temporary files without PostgreSQL; actual PostgreSQL CLI/export integration is native Windows Python 3.10.11. Cross-runtime byte equality is not claimed.

Created separate `adflow_ticket18_test` and `adflow_ticket18_history` databases, preserving earlier databases. Full entity preparation completed with seed 180018 and dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`: **10,000 users, 100 advertisers, 100,000 ads**. Before history generation, recommendations/events/request outcomes were **0/0/0**. The one-million-exposure run and identical repeat are being measured sequentially after tests completed; final results and reconciliation follow below. Ticket remains active until evidence and review are complete.
