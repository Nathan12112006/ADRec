# 47 — Build controlled benchmark execution and provenance capture

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 8 — Load testing and optimization
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 45, 46

## Scope

Automate documented ramp, 60-second warm-up and 180-second measurement with finite drain. Support 10/100/500 users, three repetitions for quoted results, explicit cold reset/warm preparation and isolated database reset.

## Dependencies

- [45 — Verify and record the dashboard phase gate](45-dashboard-gate.md)
- [46 — Implement reproducible Locust benchmark workloads](46-locust-workloads.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Performance evidence](../../adflow/issues/10-performance-evidence.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Capture host/container resources, load-generator placement, one API worker, versions, seeds and artifact/configuration IDs.
- [ ] Persist commands, raw exports, run boundaries, incomplete runs and drain limitations.
- [ ] Protect retained demo history by using an explicitly isolated benchmark database and explicit reset command.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
