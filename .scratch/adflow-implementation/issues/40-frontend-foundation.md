# 40 — Create the React dashboard shell and reliable polling

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 38, 39

## Scope

Create the React/TypeScript/Vite application with navigation, API client, reusable loading/error/empty states and accessible responsive layout. Poll every five seconds with manual refresh and pause controls.

## Dependencies

- [38 — Verify and record the Redis phase gate](38-cache-gate.md)
- [39 — Expose overview and performance summary APIs](39-dashboard-read-apis.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Dashboard demo](../../adflow/issues/09-dashboard-demo.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Pause polling while hidden and prevent overlapping requests.
- [ ] Retain last good data on failures and show stale/failed status clearly.
- [ ] Provide keyboard navigation, labeled controls and a usable narrow-screen layout.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
