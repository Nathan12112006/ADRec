# 45 — Verify and record the dashboard phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 38, 44

## Scope

Run the read-only dashboard walkthrough against the completed backend, record checks and capture any known limitations.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [44 — Package and verify the complete read-only dashboard](44-frontend-packaging.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Overview, experiment comparison and performance views operate with real API data.
- [x] Unavailable/empty/stale/provisional states are verified.
- [x] Unlock Phase 8 after technical verification; no public deployment is required.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Phase 7 technical gate passed (2026-10-09). Direct backend API and the production dashboard proxy returned matching overview values for dataset `07415efc-7c8f-5781-92d1-e922d81fa502`: 100 users, 20 advertisers, 1,000 ads, 10 recommendations, 10 durable outcomes, 10 impressions, 0 clicks and 9 exposed users. The real overview UI rendered the same values and displayed `PROVISIONAL`; this is expected because event cohorts remain open for 24 hours. The real experiment list rendered its empty state before experiment setup. Existing ticket 44 mock-backed failure injection verified unavailable recovery, stale-data retention/warning, pause/resume, hidden-page suspension and responsive/accessibility behavior.

To exercise the populated detail page, validated the existing ticket 23 feature corpus in the current Docker serving runtime, then explicitly trained, evaluated, packaged and load-checked a compatible CTR bundle under ignored local artifacts `artifacts/ctr-ticket45-docker/{model,evaluation,bundle}`. Model ID `9a63c4522aa1e49409284e47ba352edf7ba32c0d67b2ccc55c721d758b940220`; training used 700,000 train and 150,000 validation rows, validation-only regularization selection, no final-test tuning, and recorded full source/runtime hashes. Temporarily mounted the bundle read-only into the backend. Created and started experiment `d640e3f7-b023-42e9-a014-d075510c0eb3` (50/50, interest-overlap vs expected-value, exact retrieval), then sent simulator run `7afb35f3-954d-4520-89db-fae90940e9ca` at 2 opportunities/s for 30 seconds. It completed 60/60 with no failures/retries: 34 control and 26 treatment selections/impressions, 1 and 2 clicks respectively. Stopped the experiment after 49 seconds; its retained results report the cohort as provisional, no significance test, both variants, and durable CTR/revenue/fallback summaries. The actual browser detail view rendered the API-returned comparison, differences/lifts and fallback diagnostics. Observed CTR/revenue differences are descriptive synthetic sample outcomes only, not a winner or performance claim.

The backend remains available with this verified runtime-compatible model loaded from the read-only local bundle mount, which allows continued experiment inspection. The test experiment is stopped; its durable comparison history is retained. No public deployment, test database reset or volume deletion occurred. An earlier failed synthetic run before migration 0005 contributed expected pre-fix error samples to process-local telemetry; no durable outcomes/events were written for that failed run.
