# 14 — Add the HNSW candidate-retrieval comparison

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 10, 12, 13

## Scope

Implement one CPU IndexHNSWFlat option using the same vectors, ID mapping, artifact validation and eligibility pipeline as Flat. Expose documented build/search settings for controlled comparison; retain exact as the serving default pending measured promotion.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [12 — Build and reload exact FAISS index snapshots](12-flat-index-artifacts.md)
- [13 — Implement current eligibility filtering and exact fallback](13-eligibility-backfill.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Exact/approximate options share candidate/result interfaces and bounds.
- [ ] Tests tolerate boundary-tied membership but preserve eligible/distinct results and ordering.
- [ ] Record graph/build/search settings and costs; defer IVF/compression/GPU.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
