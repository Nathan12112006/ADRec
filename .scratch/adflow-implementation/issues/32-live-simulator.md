# 32 — Build reproducible API-driven demo traffic and edge scenarios

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
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

- [x] Reruns/new IDs do not replay past traffic; retries cannot inflate events/accounting.
- [x] No-ad/validation/failed delivery are reported, not converted into negative labels; summaries show attempts/rate/completion.
- [x] Both variants can be demonstrated, with live totals separated from offline history and backend-derived attribution.

## Comments

Added the `adflow-simulate` CLI with a two-minute/five-opportunities-per-second default, configurable rate/duration/seed/base URL, and a fresh UUID per invocation. Stable run-scoped idempotency keys identify opportunities; bounded retries preserve keys and recommendation IDs, so a lost response replays the same API result and accepted event retries do not add another event. The simulator calls the recommendation endpoint, confirms an impression, then independently samples and sends a click using the shared `click-world-v1` generator. Click outcomes do not use ranking score or experiment variant. No-ad, API validation failures, and delivery failures are separate from click labels. Summaries include attempts, achieved rate, completion, retries, errors, accepted events, and experiment variants returned by the API; live totals are labeled separately from offline history.

`duplicates` resends the same event payload to demonstrate deduplication. `no-interest` and `no-ad` draw only from matching existing profiles. They exit without sending traffic when no such profiles exist; the ordinary seed generator creates users with at least one interest and active inventory, so these edge scenarios require a prepared dataset. The API remains authoritative for assignment and event acceptance.

Verification from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_simulator.py backend/tests/unit/test_history_outcomes.py -q
backend/.venv/Scripts/python.exe -m mypy backend/app/simulator backend/tests/unit/test_simulator.py
backend/.venv/Scripts/python.exe -m ruff check backend/app/simulator backend/tests/unit/test_simulator.py
backend/.venv/Scripts/python.exe -m ruff format --check backend/app/simulator backend/tests/unit/test_simulator.py
```

Results: 8 tests passed; mypy, Ruff lint, and formatting checks passed. Unit coverage verifies fresh run-scoped identity, no-ad/no-interest request paths, attribution from the backend response, duplicate event count separation, and stable identity across transient retries. README documents setup and scenario requirements.
