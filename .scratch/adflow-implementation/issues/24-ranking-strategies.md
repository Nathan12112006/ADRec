# 24 — Implement interchangeable V1 and V2 ranking strategies

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 23

## Scope

Add the shared strategy interface and deterministic ordered scoring. V1 uses overlap/bid/ID without inference. V2 invokes one candidate batch and uses CTR*bid, then overlap/bid/ID ties. Validate probabilities/bids and preserve zero-score eligibility; no second auction/blending stage.

## Dependencies

- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Formula/tie/zero/all-zero/no-interest/invalid-data tests cover both strategies.
- [ ] V1 never needs the model; V2 calls once and keeps candidate/probability alignment.
- [ ] Explain score units, numerical comparison and cost without claiming guaranteed lift.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
