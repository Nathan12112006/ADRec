# 33 — Verify and record the experimentation phase gate

Status: ready-for-agent
State: open
Type: task
Kind: verification
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 26, 28, 31, 32

## Scope

Run assignment/lifecycle/concurrency/cohort/metric/failure regressions and the API simulator walkthrough. Save reconciled results with actual versions, errors and provisional status.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [28 — Expose validated experiment create/start/stop/list APIs](28-experiment-management.md)
- [31 — Implement cohort-based experiment result aggregates](31-experiment-results.md)
- [32 — Build reproducible API-driven demo traffic and edge scenarios](32-live-simulator.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Both variants appear with correct counts and stable treatment; no exact finite allocation or lift promise.
- [ ] Start/stop/replay/late-click behavior and telemetry limitations are documented.
- [ ] Offer the experiment learning checkpoint; unlock Phase 6 after this technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
