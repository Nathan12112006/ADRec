# 18 — Generate independent historical exposure and click outcomes

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
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
