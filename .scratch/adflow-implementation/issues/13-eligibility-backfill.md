# 13 — Implement current eligibility filtering and exact fallback

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 10, 11, 12

## Scope

Batch-load current ad/advertiser metadata, filter distinct eligible results, and expand queries to a configured bound before exact-current-inventory fallback. Mark stale catalog snapshots; handle missing/corrupt/incompatible indexes visibly. Provide empty-interest bid/ID fallback and no-ad/error separation.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [11 — Define versioned topic vectors and the retrieval result contract](11-topic-vectors.md)
- [12 — Build and reload exact FAISS index snapshots](12-flat-index-artifacts.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests cover ad/advertiser deactivation, missing IDs, new catalog data, limited inventory and candidate caps.
- [ ] Missing/stale artifacts and insufficient filtered results use marked exact fallback; DB failure stays 503.
- [ ] Selection-time eligibility remains enforced; fallback cost is not reported as nominal ANN performance.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
