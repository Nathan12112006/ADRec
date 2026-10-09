# 40 — Create the React dashboard shell and reliable polling

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 7 — Dashboard
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Pause polling while hidden and prevent overlapping requests.
- [x] Retain last good data on failures and show stale/failed status clearly.
- [x] Provide keyboard navigation, labeled controls and a usable narrow-screen layout.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Created the React/TypeScript/Vite application, pinned `package-lock.json`, backend API proxy, typed API client, shared page shell, responsive navigation/layout, and reusable loading/empty/error/stale UI. `usePolling` requests immediately then schedules each next request five seconds after completion, uses an in-flight guard, aborts on hidden/pause/unmount, exposes manual refresh, and retains last successful data on failure. Keyboard-focus styling, semantic navigation, labeled buttons, status announcements, and reduced-motion handling are included. Commands: `npm run build` and `npm run lint` from `frontend/` both pass with no diagnostics. Browser behavior is scheduled for the dashboard phase walkthrough after the real views are complete.
