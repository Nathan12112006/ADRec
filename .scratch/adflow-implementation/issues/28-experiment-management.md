# 28 — Expose validated experiment create/start/stop/list APIs

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 26, 27

## Scope

Implement draft creation, start, stop and list APIs with draft->running->stopped transitions and no resume. Atomically reject concurrent/invalid starts or running-config edits; validate allocation, supported settings and pinned model availability.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [27 — Persist experiments and stable synthetic-user assignment](27-experiment-schema-assignment.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Test valid transitions, missing IDs, malformed config, second starts and model-unavailable activation.
- [ ] Stopped records remain available; management APIs add no admin UI.
- [ ] Document commands and preserve exact-retrieval fallback allowance.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
