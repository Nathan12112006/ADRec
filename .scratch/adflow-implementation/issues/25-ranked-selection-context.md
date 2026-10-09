# 25 — Persist coherent ranked selections and explicit response context

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 05, 23, 24

## Scope

Wire strategy selection into the recommendation workflow with eligibility/bid revalidation and coherent immutable selection metadata. Expose score meaning, strategy/retrieval/model/feature versions and null V1 CTR. Model-required nonempty V2 requests fail 503 without substitution.

## Dependencies

- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)
- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)
- [24 — Implement interchangeable V1 and V2 ranking strategies](24-ranking-strategies.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests reproduce a lower-bid expected-value winner, coherent changed-metadata handling and saved-result replay.
- [x] Empty candidates follow no-ad without model inference; invalid model/outputs preserve failure semantics.
- [x] Click credits still use captured bid, never expected-value score or a clearing price.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implementation started from `97225325e32bb5af3ec89c6ce754dfe4543ad921` on 2026-10-08,
after dependencies 05, 23 and 24 were done. Nathan confirmed public recommendation
workflow/HTTP seams covering ranked metadata, changes during selection, replay,
empty/model failure behavior and impression/click accounting before new tests.

- The workflow accepts an interchangeable ranking strategy, defaults to V1, ranks detached retrieved candidates using locked user context, and directly chooses the first scored ad. It revalidates/locks the winning ad and advertiser before saving score, bid, features and model provenance as one immutable JSON selection. Bid, interest/category, activity or advertiser changes retry the complete transaction/retrieval/ranking, bounded at three attempts. V2 calls one batch per attempt; a stale attempt is not persisted. No extra auction/scoring pass is added.
- Added validated `ADFLOW_RANKING_STRATEGY=interest-overlap|expected-value` server configuration, default V1, with environment/Compose examples. The existing recommendation endpoint uses the configured strategy and process-resident CTR adapter. Request bodies remain user ID only; experiment assignment/routing remains later work. Responses expose score/meaning, strategy/version, overlap, captured bid, retrieval diagnostics and model ID/version/feature version. JSON-safe request logs expose score/meaning, strategy/version and model ID/version/feature version. V1 predicted CTR/model fields are null.
- Replay looks up the saved opportunity before retrieval/ranking, preserving its decision across model, strategy, bid/category and eligibility changes. Empty V2 inventory saves replayable no-ad without requiring a model. Nonempty unusable-model/invalid-output V2 returns typed `ctr_unavailable`/503 without silently substituting baseline or saving an opportunity. Explicitly switching configuration can allow a later retry to choose baseline; saved decisions still replay under any configured strategy.
- Tests observed red/green for the new service strategy parameter, configured V2 HTTP winner and zero-score replay serialization. Persisted decimal strings that represented integral/zero values initially reloaded through the integer union branch; preferring Decimal for string validation fixes this while retaining integer V1 scores. Older saved V1 JSON remains readable via null defaults for additive context fields. No database migration or accounting change is needed.
- New public workflow/HTTP tests cover a lower-bid expected-value winner; one aligned real CTR-adapter batch; winner bid/interests/category/activity/advertiser edits during prediction via the external estimator/database boundary; bounded repeated edits with retryable failure; replay with unavailable/new strategy and changed inventory; zero-value JSON replay; safe model-unavailable/NaN/count/exception failures; baseline availability and failed-key retry; empty/no-ad replay; and impression/duplicate-click credit at the original captured bid, never score/current bid. Existing HTTP test stubs were updated only to accept the added strategy argument.
- Focused workflow/lifecycle/retrieval/HTTP regression: **74 passed in 17.99s**; strict mypy **94 source files clean**. README documents score units/serialization, configuration, locking/retry/replay, additive compatibility and captured-bid accounting without observed CTR/revenue lift claims.
- Final full PostgreSQL-enabled regression: **583 passed in 196.53s**, isolated `adflow_ticket25_test`. Mypy **94 source files clean**; Ruff lint/format pass; Alembic reports **no new upgrade operations**; wheel/sdist build and offline lock validation (**65 packages**) pass. Docker config/build and evidence lint/format pass. [Exact commands](../evidence/ticket25/commands.md) retain configuration and reproduction instructions.
- [Native actual-HTTP smoke](../evidence/ticket25/native-http-smoke.json) passes under CPython 3.10.11 using the retained full model `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`. [Docker actual-HTTP smoke](../evidence/ticket25/docker-http-smoke.json) passes under CPython 3.12.15 using its explicitly prepared 10,000-exposure fixture model `9c2f8ff8bbf9f410bde944c512548fc7fde1c6a854b62d718372ab26de15a2e2`. [Smoke script](../evidence/ticket25/http-smoke.py) migrates/seeds only the isolated verification database, launches the actual Uvicorn app, makes HTTP recommendation/event requests, verifies JSON-safe logs and stops the test server. It selects the music ad with bid1 over a bid2 alternative; native probability/score `0.04424964327783697` / `0.044249643277836970000`, Docker `0.05647824691200216` / `0.056478246912002160000`. Replay stays identical after bid99/deactivation edits; duplicate clicks return the same single captured-bid credit `1.0000`. This is correctness evidence, not observed-effectiveness/performance evidence or cross-runtime model equality.
- Docker image: `sha256:d98ca708446b0fa3abd2ccf9fe938adeab2430992b73da3683b171f4c53e7ad2`. Docker uses a separate unexposed `adflow-ticket25-postgres` container/network, so no development PostgreSQL port/data was replaced. Initial native HTTP assertions passed but temporary-log cleanup briefly failed on Windows; stopping the spawned test-server process tree before cleanup fixed the evidence script, and the complete native smoke passed again. No application fix was required for that cleanup issue.
- A manual environment-settings check confirmed unknown ranking strategies are rejected with a safe configuration diagnostic. Native PostgreSQL and the isolated Docker verification PostgreSQL container are stopped; all databases, Docker data/container/network and original model/history artifacts remain retained. The verified temporary directory left by the first smoke was cleaned after its test process exited. No human learning checkpoint is certified by this ticket.

### Standards

Independent read-only review against task-start `97225325e32bb5af3ec89c6ce754dfe4543ad921`, including untracked tests/evidence: 1 minor documentation mismatch, 0 heuristic findings. The ticket initially overstated which response fields also appear in logs; corrected to list the response and logged fields separately. The reviewer confirmed the correction: **0 remaining documented violations and 0 heuristic findings**. No application change was needed. Naming, dependency composition, transaction/replay separation, decimal serialization, tests and actual smoke evidence otherwise pass.

### Spec

Independent read-only review: **0 actionable findings**. Coherent persistence, metadata/eligibility revalidation, bounded retry, explicit context, immutable replay and nonempty V2 failure semantics satisfy ticket 25. Tests and actual native/Docker HTTP evidence cover changed metadata, zero-score serialization, model errors, no-ad replay and captured-bid accounting. Experiment routing remains outside scope. The reviewer did not rerun tests.
