# 54 — Run final correctness and build verification

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 9 — Final polish
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 51, 52, 53

## Scope

Run appropriate backend/integration/frontend builds and end-to-end demo regressions against final artifacts, including lifecycle races, failure paths and attribution.

## Dependencies

- [51 — Verify and record the performance evidence phase gate](51-performance-gate.md)
- [52 — Verify explicit artifact preparation and fresh Docker startup](52-fresh-setup-walkthrough.md)
- [53 — Finish reviewer documentation, diagrams and real screenshots](53-readme-reviewer-evidence.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Record exact checks, environment, artifact versions and failures/fixes.
- [ ] Validate final migrations and documented fresh setup are reproducible.
- [ ] Report remaining limitations without presenting unrun checks as passed.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
