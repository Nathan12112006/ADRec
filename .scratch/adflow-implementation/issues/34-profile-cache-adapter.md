# 34 — Implement bounded Redis profile-cache access

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 6 — Redis
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33

## Scope

Cache versioned user-profile JSON only, with schema validation, dataset namespaces, atomic expiry and downward jitter from a maximum 60-second TTL. Use a shared bounded connection pool, short 100ms connect/socket timeouts and zero automatic retries.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Malformed, stale-version and absent entries fall through to PostgreSQL; misses are not negatively cached.
- [ ] Cache hits do not renew expiry; tests exercise expiry, serialization and pool exhaustion.
- [ ] Cache telemetry distinguishes hits, misses, invalid entries, errors and bypasses.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
