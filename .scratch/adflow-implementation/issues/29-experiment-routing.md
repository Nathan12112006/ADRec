# 29 — Route recommendations with immutable experiment attribution

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 25, 26, 27, 28

## Scope

Choose assigned strategy under a consistent start/stop/selection boundary and persist experiment/variant/executed versions with outcomes. Use configured default outside a running experiment; preserve attribution on replay and events after stopping.

## Dependencies

- [25 — Persist coherent ranked selections and explicit response context](25-ranked-selection-context.md)
- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [27 — Persist experiments and stable synthetic-user assignment](27-experiment-schema-assignment.md)
- [28 — Expose validated experiment create/start/stop/list APIs](28-experiment-management.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Racing starts/stops cannot save ambiguous treatment; later events retain the original variant/cohort.
- [ ] Treatment model loss yields 503, never baseline substitution; empty/no-ad behavior remains correct.
- [ ] No client-provided variant can rewrite attribution; retrieval configuration is shared.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
