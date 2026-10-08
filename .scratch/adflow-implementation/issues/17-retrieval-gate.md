# 17 — Verify and record the candidate-retrieval phase gate

Status: ready-for-agent
State: open
Type: task
Kind: verification
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 10, 16

## Scope

Execute retrieval/vector/ID/reload/filter/fallback checks and save comparison evidence, preparation commands and an explanation of exact scans versus bounded downstream ranking. Keep exact if ANN fails its gate.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [16 — Measure exact and approximate retrieval quality and cost](16-retrieval-benchmarks.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Canonical Phase 2 checks pass and evidence records actual dataset sizes and modes.
- [ ] README/setup explains rebuild/fallback and measured tradeoffs.
- [ ] Offer the retrieval learning checkpoint and unlock Phase 3 only after this technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
