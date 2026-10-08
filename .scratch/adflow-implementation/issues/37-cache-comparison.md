# 37 — Measure profile-cache behavior under reproducible access patterns

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33, 35, 36

## Scope

Run focused cold/warm and uniform/hot-user cache comparisons with fixed data, ranking and retrieval settings. Record actual cache counters, elapsed time and outage behavior; this is component evidence before the full load-test phase.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [35 — Integrate cache fallback and post-commit invalidation](35-cache-serving-invalidation.md)
- [36 — Expose dependency capabilities and disposable Redis configuration](36-cache-health-operations.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explicitly reset cold cache and describe how warm cache was populated.
- [ ] Include provenance, database read reduction and failed-cache fallback checks.
- [ ] Do not claim whole-service speedup from component timing; document observed limitations.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
