# 26 — Verify and record the ranking phase gate

Status: ready-for-agent
State: done
Type: task
Kind: verification
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 23, 25

## Scope

Run all ranking and lifecycle regression checks and compare strategies on identical candidate sets. Save algorithm explanation, response examples and actual outcomes without comparing incompatible raw-score averages.

## Dependencies

- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)
- [25 — Persist coherent ranked selections and explicit response context](25-ranked-selection-context.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Formula/batch/tie/replay/accounting/model-failure checks pass.
- [x] No unsupported auction, blending or score-normalization layer has been added.
- [x] Offer the ranking learning checkpoint and unlock Phase 5 after this technical gate.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Technical verification started on 2026-10-08 from `56497fff7ca4ac6b566b4052e8d2c5ce6d028d83`, after dependencies 23 and 25 were done. Existing agreed ranking/workflow/HTTP seams cover this gate; no new application feature or test seam is planned.

- [Gate results](../evidence/ticket26/results.md) explain overlap versus predicted CTR times bid, units, deterministic ties, zero bids, one batch per attempt, coherent snapshot/retry/replay, captured-bid accounting and O(C log C)/O(C*F) costs. Code-path inspection confirms no second auction, blending, score normalization or new charging layer. No production code/schema/dependency/model change was required.
- [Frozen comparison](../evidence/ticket26/comparison.json), reproduced by [compare-strategies.py](../evidence/ticket26/compare-strategies.py), uses seed26 to select 200 retained users and the same declared ordered 500-ad pool for each strategy/user. Exact IDs/context hashes and original file hashes are retained and unchanged. The full native model remains `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`, dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`. Candidate pools are offline uniform samples of frozen eligible ads, not live FAISS retrieval; existing retrieval regression remains separate.
- Both strategies chose the same ad for 103 users, different ads for 97. Independent `click-world-v1` behavior with original seed18 supplies 100 paired sampled outcomes per user/strategy: V1/V2 record **797/941 clicks over 20,000 sampled impressions each**, sampled observed CTR **0.03985/0.04705**, simulated revenue **3931.5300/4619.3400** and per-impression revenue **0.1965765/0.230967**. Raw scores with incompatible units are not averaged. These are offline synthetic samples reusing the training entity population/assumptions and repeated within-user opportunities, not live experiment observations, causal lift, independent-user evidence or real-world effectiveness. No model/final-test tuning occurred.
- [Native response examples](../evidence/ticket26/response-examples.json), reproduced by [response-examples.py](../evidence/ticket26/response-examples.py), use real ASGI HTTP/startup/model/PostgreSQL dependencies without overrides, in isolated `adflow_ticket26_examples`. V1 selects overlap1/bid0/score1 with null CTR and credit0; V2 selects bid100/probability0.017334713604441356/score1.7334713604441356000000 and credit100. Both replay unchanged after bid999/deactivation and configured V2 model unavailability; duplicate clicks return one captured-bid credit. First fixture attempt used unsupported retrieval topic `unknown`; corrected to `cars` and reran successfully, without application changes or data deletion.
- Focused formula/batch/tie/model/lifecycle regression: **162 passed in 52.25s**. Full PostgreSQL-enabled regression in isolated `adflow_ticket26_test`: **583 passed in 179.91s**. Strict mypy **94 source files clean**; Ruff lint/format pass; Alembic **no new upgrade operations**; wheel/sdist build and offline lock check (**65 packages**) pass. [Exact commands](../evidence/ticket26/commands.md) retain configuration/reproduction and check scope.
- [Docker actual socket-HTTP smoke](../evidence/ticket26/docker-http-smoke.json) passed using the retained isolated ticket25 PostgreSQL container/network and explicitly prepared 10,000-exposure container-runtime fixture model `9c2f8ff8bbf9f410bde944c512548fc7fde1c6a854b62d718372ab26de15a2e2`. Score0.056478246912002160000 remains coherent with bid1, replay is identical after bid99/deactivation, and duplicate clicks credit1 once. CPython native/Docker **3.10.11/3.12.15**. Rebuilt Docker image `sha256:9d5ca319e999288790764e976f6205ea1c3113e876963fcdd96a3cfb38879ab6`; Compose config/build and evidence lint/format pass. Initial Docker smoke failed readiness with connection refused; the original utility did not retain startup logs, so the cause is not established. The reused ticket25 evidence utility now allows 600 attempts with 0.1 seconds between polls and includes server logs in readiness failures. Complete rerun passed. No full-scale Docker, cross-runtime equality or latency claim is made.
- Offered [ranking learning checkpoint 60](60-learning-ranking.md): explain lower-bid winners, units/ties, no second auction, unavailable models and captured bid, then direct a small ranking-input/probability change and verify it. Ticket60 remains open; no actual human explanation/change/understanding is certified. Phase5's technical dependency unlocks only once this gate is marked done after review.
- Native PostgreSQL and isolated Docker verification PostgreSQL started for this gate were stopped cleanly after checks. All databases, Docker data/container/network, original frozen model/history artifacts and durable history remain retained.
- Spec review caught an initially missing separate sorting measurement. Added [public-call component measurement](../evidence/ticket26/measure-components.py) and [raw samples](../evidence/ticket26/component-timings.json): first frozen user/1,50,500 ads, one thread/caller, 10 warmups and 50 samples, CPython3.10.11/AMD64 Family23 Model104/16 logical CPUs. V1/V2 profiled production sorting median milliseconds: **0.004900/0.012450**, **0.095250/0.120900**, **1.072850/1.403600**. Feature and inference phases are separately measured through the public CTR adapter; P95/all samples and limitations remain in the report. Sort measurements include profiler overhead and are not comparable uninstrumented request timings. No production instrumentation, speed target or new test seam was introduced.

### Standards

Independent read-only review against task-start `56497fff7ca4ac6b566b4052e8d2c5ce6d028d83`, including untracked evidence and the added measurement script: **0 documented violations, 0 heuristic findings**. Tracker/domain conventions, identical-pool inputs, provenance, actual responses/accounting and separation of human learning pass. Component measurement uses public rank calls with explicit profiling scope; observed values match saved samples. No heavy checks were repeated by the reviewer.

### Spec

Independent read-only review initially found one missing separate sorting measurement required by the governing ranking contract. Added reproducible production-sort measurements separate from features/inference, including all samples, candidate counts, runtime/hardware, warmups and overhead limitations. Reviewer confirmed resolution: **0 remaining actionable findings**. Identical-pool comparison, synthetic limits, lifecycle examples, canonical regression and open checkpoint otherwise satisfy ticket26, without unsupported auction/blending/score normalization.

Review total: Standards 0; Spec 0 remaining. All technical acceptance criteria pass; **Phase4's ranking gate is complete and ticket27/Phase5 is unblocked**. Ticket60 remains open for actual human work. Saved comparison totals and original input hashes reconciled after the checks. Whitespace/evidence lint/format pass. The implementation skill's commit is on the current `main` branch.
