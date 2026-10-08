# 11 — Define versioned topic vectors and the retrieval result contract

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 10

## Scope

Implement binary user-interest and ad interest/category-union vectors with normalized cosine semantics and versioned vocabulary order. Define CandidateRetriever results with IDs, current metadata, similarity when applicable, modes/versions/counts/timing/fallback reasons; validate configurable limits.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests cover normalization, category deduplication, vocabulary/dimension/finite-value validation and invalid zero-vector ads.
- [ ] Empty-interest users have an explicit nonpersonalized path; limits are positive/bounded.
- [ ] No bids or artificial dimensions enter vectors; document similarity versus ranking overlap.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
