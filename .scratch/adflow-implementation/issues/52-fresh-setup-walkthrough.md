# 52 — Verify explicit artifact preparation and fresh Docker startup

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 9 — Final polish
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 51

## Scope

Run the documented fresh-checkout flow: configuration, build, migrations, seed, index build, history generation, training and startup with explicit preparation commands.

## Dependencies

- [51 — Verify and record the performance evidence phase gate](51-performance-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Application startup does not silently generate datasets or train models.
- [ ] Document small demo and full evidence dataset choices, prerequisites and artifact locations.
- [ ] Verify health, recommendation/events, experiment start/stop, simulator and dashboard in Docker; record actual commands/results.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
