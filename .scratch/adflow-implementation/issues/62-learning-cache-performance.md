# 62 — Explain and modify caching and performance measurement

Status: ready-for-human
State: open
Type: task
Kind: human-checkpoint
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 51

## Scope

Nathan explains PostgreSQL authority, cache expiry/invalidation races, degraded operation and benchmark populations, then makes or directs a small relevant change.

## Dependencies

- [51 — Verify and record the performance evidence phase gate](51-performance-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explain latency versus throughput, closed-loop users and reproducible comparisons.
- [ ] Verify the change and any resulting claims with relevant checks.
- [ ] Record actual human review and known measurement limits.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
