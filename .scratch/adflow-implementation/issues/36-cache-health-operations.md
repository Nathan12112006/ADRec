# 36 — Expose dependency capabilities and disposable Redis configuration

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33, 35

## Scope

Add Redis to Compose with 128MB LRU eviction and no persistence. Expose cache degradation and index/model capability status separately from database readiness.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)
- [35 — Integrate cache fallback and post-commit invalidation](35-cache-serving-invalidation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Database readiness alone controls ready status; Redis outage reports degradation without failing readiness.
- [ ] Index fallback and unavailable V2 model have the accepted distinct behavior.
- [ ] Document cache controls, timeout limitations, counters and hit ratio h/(h+m), null when no eligible observations.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
