# 16 — Measure exact and approximate retrieval quality and cost

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 03, 10, 14, 15

## Scope

Add reproducible component comparisons for full-ad ranking, Flat plus the same ranking and HNSW plus that ranking. Support full 100,000-ad entities, frozen query/eligibility snapshots, ties and separate fallback queries. Record provenance/build/memory/search/metadata/ranking costs.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [14 — Add the HNSW candidate-retrieval comparison](14-hnsw-option.md)
- [15 — Integrate candidate retrieval into recommendation serving](15-retrieval-serving.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Ordinary and canonical tie-aware recall, boundary tolerance and missed-superior counts are correct on fixtures; k=0 is unavailable.
- [ ] Actual scale/results are saved; only promote HNSW with lower full-retrieval P95 and at least 95% tie-aware recall.
- [ ] No ANN/full-scale/speedup claim is made for an unrun or smaller comparison.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
