# 41 — Build the live overview dashboard

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 38, 40

## Scope

Display current-dataset live impressions, clicks, CTR and simulated revenue with useful charts or summaries driven by the overview API.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [40 — Create the React dashboard shell and reliable polling](40-frontend-foundation.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Labels include time context, units and simulated-data disclosure.
- [ ] Zero values, null denominators, loading and unavailable data render distinctly.
- [ ] Displayed counts and money reconcile with API fixture and live demo responses.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
