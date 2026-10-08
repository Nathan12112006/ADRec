# 12 — Build and reload exact FAISS index snapshots

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 03, 10, 11

## Scope

Implement CPU IndexFlatIP build/load commands with stable ID mapping and manifest/checksums. Record catalog/vector/runtime/settings versions; validate complete artifacts and swap immutable references off the request path. Pin/smoke-test compatible CPU FAISS/NumPy in the actual runtime.

## Dependencies

- [03 — Generate reproducible configurable entity seeds](03-small-data-seed.md)
- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [11 — Define versioned topic vectors and the retrieval result contract](11-topic-vectors.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Normalized search, database-ID mapping and persisted reload agree on a known fixture.
- [ ] Bad checksums/schema/mapping/runtime versions are rejected without replacing a working reference.
- [ ] No live index mutation or per-request rebuilding; artifact preparation/reload commands are documented.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
