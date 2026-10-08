# 61 — Explain and modify experiment attribution

Status: ready-for-human
State: open
Type: task
Kind: human-checkpoint
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 33

## Scope

Nathan explains stable assignment, immutable configuration, lifecycle transitions, cohorts and late events, then makes or directs a small relevant change.

## Dependencies

- [33 — Verify and record the experimentation phase gate](33-experiments-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Explain metric denominators, provisional results and null lift.
- [ ] Verify assignment/attribution/accounting after the change.
- [ ] Record actual human review without asserting causal or statistical proof beyond the contract.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
