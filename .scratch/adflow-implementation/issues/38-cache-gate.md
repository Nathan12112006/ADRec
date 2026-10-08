# 38 — Verify and record the Redis phase gate

Status: ready-for-agent
State: open
Type: task
Kind: verification
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33, 37

## Scope

Run cache correctness, outage and health regressions and record the measured comparison and operating instructions.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [37 — Measure profile-cache behavior under reproducible access patterns](37-cache-comparison.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Expiry, invalidation, namespace replacement and outage behavior match the contract.
- [ ] Preserve PostgreSQL accounting and experiment regressions.
- [ ] Offer the cache/performance learning checkpoint and unlock Phase 7 after technical verification.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
