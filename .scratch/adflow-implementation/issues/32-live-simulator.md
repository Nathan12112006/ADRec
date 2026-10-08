# 32 — Build reproducible API-driven demo traffic and edge scenarios

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 18, 26, 29, 31

## Scope

Implement CLI simulation: default two minutes targeting five opportunities/sec, configurable rate/duration, fresh run IDs and stable opportunity keys/randomness. Request, confirm display, then optionally click using independent rules; bounded retries preserve identity. Separate duplicate/no-interest/no-ad scenarios.

## Dependencies

- [18 — Generate independent historical exposure and click outcomes](18-synthetic-history.md)
- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [29 — Route recommendations with immutable experiment attribution](29-experiment-routing.md)
- [31 — Implement cohort-based experiment result aggregates](31-experiment-results.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Reruns/new IDs do not replay past traffic; retries cannot inflate events/accounting.
- [ ] No-ad/validation/failed delivery are reported, not converted into negative labels; summaries show attempts/rate/completion.
- [ ] Both variants can be demonstrated, with live totals separated from offline history and backend-derived attribution.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
