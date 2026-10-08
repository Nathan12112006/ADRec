# 19 — Build shared CTR features and chronological splits

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 3 — CTR model
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 17, 18

## Scope

Implement the five accepted features from immutable historical snapshots and the same builder for serving. Produce deterministic 70/15/15 chronological impression splits with label grouping and boundaries. Exclude IDs/bid/variant/hidden probabilities, activity and historical aggregate features.

## Dependencies

- [17 — Verify and record the candidate-retrieval phase gate](17-retrieval-gate.md)
- [18 — Generate independent historical exposure and click outcomes](18-synthetic-history.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests cover overlap/category-match, empty interests, missing/unknown categoricals and snapshot stability.
- [ ] Every impression/label belongs to exactly one temporal split; no future/outcome feature leakage.
- [ ] Feature schema/version and source provenance are explicit.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
