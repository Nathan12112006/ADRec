# 24 — Implement interchangeable V1 and V2 ranking strategies

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 23

## Scope

Add the shared strategy interface and deterministic ordered scoring. V1 uses overlap/bid/ID without inference. V2 invokes one candidate batch and uses CTR*bid, then overlap/bid/ID ties. Validate probabilities/bids and preserve zero-score eligibility; no second auction/blending stage.

## Dependencies

- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Formula/tie/zero/all-zero/no-interest/invalid-data tests cover both strategies.
- [x] V1 never needs the model; V2 calls once and keeps candidate/probability alignment.
- [x] Explain score units, numerical comparison and cost without claiming guaranteed lift.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Started on 2026-10-08 after ticket 23's technical gate passed. The existing baseline
selector, detached retrieval candidates, CTR batch adapter and authoritative ranking
contract were inspected. Ticket 25 owns recommendation persistence and HTTP wiring;
this ticket adds the interchangeable ordered ranking interface only.

Nathan confirmed the test seams on 2026-10-08: public ranking results for V1/V2
formula, deterministic ties, zero/all-zero/no-interest/empty inputs, invalid data and
strategy/model/feature metadata; plus real CTR-adapter integration for aligned batch
prediction and typed unavailable failures. Tests were written only after confirmation.

Implementation will preserve decimal bids and compare unrounded expected-value
scores consistently, retaining overlap and bid snapshots with each ranked ad. V1
needs no model and reports null predicted CTR/model/feature metadata. V2 predicts
the full input batch once, checks alignment and probabilities, then sorts by expected
value, overlap, bid and ascending ID. Empty input avoids inference. Strategy selection
and persisted accounting/replay remain ticket 25 work.

Implementation and focused evidence:

- Added `app.ranking.strategies` with the shared `RankingStrategy.rank` protocol, immutable `RankingResult`/`ScoredCandidate` output, `InterestOverlap` and `ExpectedValue` implementations. Both accept detached eligible candidate mappings, validate decimal bids and distinct IDs, and return deterministic complete order. V1 preserves published `interest-overlap`/`baseline-v1`/`distinct_shared_interest_count` metadata and null CTR/model metadata. V2 invokes the real CTR adapter once in original input order, retains batch versions and bid snapshots, and orders expected value, distinct overlap, bid, then ascending ID. Empty V2 input does not invoke the model; nonempty unavailable/invalid-output models preserve typed 503 failures.
- TDD slices observed red then green for missing V1/V2 implementations, caller-context precision, empty V2 metadata/no-inference behavior, duplicate IDs and published V1 metadata compatibility. Additional specification examples cover exact 0.10*$1 vs0.02*$3, highest-CTR-alone loss, deterministic ties, zero/all-zero/no-interest cases and invalid bid/probability/count data. The controllable estimator fixture sits behind the real CTR adapter; no internal model/strategy mocks were used.
- V2 scores use `Decimal(str(probability)) * bid` under local coefficient-sized precision; exact `copy_negate` sort keys avoid caller-context rounding. JSON represents V1 primary scores as integers and V2 expected-value scores/bids as decimal strings, with numeric predicted CTR. The precision regression uses an Inexact-trapping four-digit caller context and distinct close bids; serialized ranking is not display-rounded. Score units and O(C) scoring/storage, O(C log C) sorting and O(C*F) dense model costs are documented in README. Expected-value ranking guarantees no observed CTR/revenue lift.
- Focused ranking/baseline/CTR regression: **60 passed**; strict mypy **93 source files clean**. After preserving published V1 metadata, all **30 new ranking tests passed** again and whole-backend lint/format passed. Initial lint-only line-length findings were resolved by formatting before final checks.
- [Native smoke](../evidence/ticket24/native-smoke.json), reproduced by [runtime-smoke.py](../evidence/ticket24/runtime-smoke.py), loads the retained full native pipeline, compares V1/V2 over the same two candidates, verifies complete JSON round-trip, zero-bid eligibility and typed unavailable/empty behavior. V1 selects overlap ad9 with bid0; V2 selects ad4 with bid100 and probability0.017220677569718144, expected score1.722067756971814400. This demonstrates differing selection, not observed-outcome lift or a performance measurement. Native CPython3.10.11, model `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`.
- [Docker smoke](../evidence/ticket24/docker-smoke.json) passes the same ranking/serialization/failure checks using a small model explicitly trained, evaluated, packaged and reloaded inside CPython 3.12.15. Final image `sha256:4bd58c90c029b7c3458ef5e3ec2e49e87a3a30859e42ab01104e4a7309b02223`. Native/Docker identities need not match; no cross-runtime artifact reuse or full-scale Docker quality/performance is claimed. [Exact commands](../evidence/ticket24/commands.md) include focused/full tests, native/Docker smoke and build/configuration checks.
- Final full regression: **568 passed in 136.55s**, including PostgreSQL integration in isolated `adflow_ticket24_test`. Mypy: **93 source files clean**; Ruff lint/format pass; Alembic: **no new upgrade operations**; wheel/sdist builds and offline lock verification (**65 packages**) pass. Docker configuration/build and evidence lint/format pass. All acceptance criteria are complete. PostgreSQL started for verification was stopped cleanly afterward; original data/artifacts and test databases remain retained. No learning checkpoint is certified by this implementation.

### Standards

Independent read-only code-review against task-start `6d8654330ea90926f46ba001c466d69f7e5af166`, including untracked files: **0 documented violations, 0 heuristic findings**. Naming, ticket boundaries, decimal precision, interface validation and saved evidence match repository conventions. Shared validation/ordering avoid meaningful duplication; no actionable smells were found. Full regression results were recorded by the parent after the reviewer inspected implementation and focused/smoke evidence; the reviewer did not rerun tests.

### Spec

Independent read-only review: **0 actionable findings**. Both formulas and deterministic tie rules, null V1 metadata/no inference, aligned single V2 batch, decimal scores, typed model failures and zero-score eligibility satisfy the owning contract. Tests and native/Docker evidence cover the edge cases. Persistence/API wiring remains ticket 25 scope. No scope creep or missing behavior was found.

Review total: Standards 0; Spec 0; neither axis has an outstanding issue. The implementation skill's commit is on the current `main` branch. Ticket 24 is complete and unblocks ticket 25.
