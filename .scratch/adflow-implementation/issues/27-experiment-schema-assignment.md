# 27 — Persist experiments and stable synthetic-user assignment

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 26

## Scope

Add versioned experiment schema/migrations, stored salt/digest mapping, default 50/50 allocation and pinned ranking/model/feature/retrieval configuration. Enforce one running experiment in PostgreSQL; keep assignments stable across requests/restarts.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Known assignments and split boundaries reproduce across processes; user count is not forced exactly 50/50.
- [ ] Schema preserves historical experiments and immutable treatment identity.
- [ ] Migration/constraint tests include concurrent running-experiment conflicts.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
