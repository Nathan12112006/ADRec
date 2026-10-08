# What staged delivery plan proves completion and interview readiness?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 02, 09, 10

## Question

Consolidate resolved decisions into the build handoff and phase acceptance gates, without duplicating decision detail. Decide optional-feature cuts, dependency/setup lifecycle, Docker startup and seed/model/index preparation, lint/type/test checks, README/demo requirements, and explain-and-modify checkpoints. Revisit whether public hosting belongs in this release; if yes, create the hosting decisions and research needed before closing the map. Define what counts as finished and which evidence must exist.

## Comments

### Final confirmation

Nathan accepted the nine-phase order with verified gates, explicit preparation commands before ordinary Docker startup, Docker-only release with public hosting as a separate follow-up, explain-and-modify checkpoints, retained durable history without automatic cleanup, and finished-project evidence requirements.

Claimed at Nathan's request on 2026-10-07. All prerequisite decisions are resolved. Starting the final live discussion of staged acceptance, reviewer setup, hosting scope, interview checkpoints, and implementation handoff.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

## Answer

Resolved with Nathan on 2026-10-07. The planning destination is reached: required pre-build decisions are settled. [AdFlow implementation handoff](../spec.md) indexes the canonical contracts without replacing them. This resolution does not mark application implementation or learning checkpoints complete.

### Delivery order and phase gates

Implement in the original nine-phase order. Complete and record each phase's relevant checks before starting the next; preserve working code and use focused changes. Start Docker support, setup instructions, and explanations in Phase 1 rather than postponing all of them to polish.

| Phase | Work and canonical decision | Evidence before advancing |
| --- | --- | --- |
| Core backend | [What is the smallest reliable Phase 1 backend?](02-phase-one-boundary.md#answer), using [What constitutes a served ad and a valid attributed click?](01-serving-and-events.md#answer) | Fresh migrations/seed, API lifecycle walkthrough, PostgreSQL integration and unit checks, local/Docker startup, documented exact commands |
| Candidate retrieval | [What retrieval contract makes FAISS useful and measurable?](04-candidate-retrieval.md#answer) | Validated index/reload/fallback, eligibility/tie tests, exact/ANN comparisons and actual scale evidence as specified |
| CTR model | [What CTR model and evaluation contract are credible for synthetic data?](05-ctr-evaluation.md#answer), with [How will synthetic data and simulated traffic provide honest evidence?](03-synthetic-world.md#answer) | Reproducible historical artifacts/training/evaluation, metrics versus baseline, compatible pipeline reload, batch/failure tests |
| Ranking and selection | [How will two ranking strategies choose winners without redundant scoring?](06-ranking-economics.md#answer) | Formula/tie/zero-bid checks, one batch prediction, coherent saved score/bid/attribution and replay |
| Experiments | [What experiment contract makes comparisons interpretable?](07-experiment-contract.md#answer) | Assignment/lifecycle/metric tests and API-driven simulator walkthrough with count reconciliation |
| Redis | [What should Redis cache and how will dependency failures behave?](08-cache-and-failures.md#answer) | TTL/namespace/failure/recovery checks and like-for-like enabled/disabled measurements |
| Dashboard | [What is the smallest dashboard that demonstrates the complete system?](09-dashboard-demo.md#answer) | Real API integration, responsive/accessibility/state/polling checks, TypeScript/build checks, walkthrough reconciliation |
| Load testing and optimization | [What measurements will substantiate the performance claims?](10-performance-evidence.md#answer) | Reproducible runs/exports/provenance, documented saturation, profiling-led changes and comparable reruns where warranted |
| Final polish | This delivery decision | Verified reviewer setup, final relevant checks, documentation/diagram/screenshots/limitations, evidence-backed claims and learning review |

Historical labels arrive when model development needs them; live simulation arrives when the lifecycle/experiments need it. The small Phase 1 seed must not depend on the full history, model, or experiment subsystem. Component measurements begin in their phases; Phase 8 consolidates final load evidence rather than inventing earlier results.

### Reviewer setup and artifact lifecycle

Document explicit preparation commands for database migrations and the small entity seed, followed by ordinary docker compose up operation. Provide separate commands for index builds, historical generation, offline model training/evaluation, experiment creation/start/stop, traffic simulation, and load tests as those capabilities arrive.

Do not silently create large history, overwrite data, or retrain models during startup. Fresh startup can serve baseline recommendations after preparation; CTR-required serving has the agreed unavailable-model behavior until its compatible artifact is prepared. Preserve dataset/model/index/feature manifests and document paths, compatibility checks, and rebuild procedures. Default small-data setup remains easy to reproduce; full-scale preparation is explicit and labeled.

Keep environment examples, local backend development, Docker operation, isolated integration-test setup, and exact check commands current at each phase. Verify compatible dependencies and runtime behavior during implementation; planning research is not proof of a successful install.

### Release boundary and retention

Finish this release as a reproducible Docker demo. Public hosting is a separate follow-up effort, with its own audience, cost, operations, and access decisions if requested later. No hosting account/provider research or deployment is required to complete this map or core release.

Preserve the existing scope cuts: no conversions/advertiser reporting, blended scoring/auction pricing, significance/winner automation, overlapping experiments, browser administration, live profile-edit APIs, or advanced distributed infrastructure. They do not silently re-enter final polish.

Retain durable recommendation/event/request-outcome history without automatic cleanup. Expired-key/event identity guarantees remain intact. Use isolated benchmark/test databases for repeatable resets, and document reset scope rather than clearing development history as part of tests. Production retention/archival policy is deferred beyond this local release. Dataset replacement follows the agreed namespace/traffic-pause rules.

### Explain-and-modify checkpoints

After major components work, ask Nathan to explain the mechanism and make a small verified change. Record actual checkpoint outcomes and gaps; never certify understanding merely because code/tests exist. Suggested concrete exercises are:

| Area | Explain | Small change to verify |
| --- | --- | --- |
| Lifecycle/storage | Why request keys, uniqueness, and transactions prevent duplicate attribution/accounting | Add or adjust a retry/concurrency case and confirm one selection/event credit |
| Retrieval | Topic vectors, exact versus approximate search, ties, filtering, and fallback | Change candidate limit/search setting and measure returned quality/cost |
| CTR | Feature meaning, leakage, chronological splits, probabilities, and baseline comparison | Remove a feature or change regularization using validation data, not the final test |
| Ranking | Overlap versus expected value, units, zero bids, and captured-bid accounting | Work through a lower-bid winner and verify a deterministic tie case |
| Experiments | Stable assignment, exposure versus assignment, late events, and immutable treatment | Trace a click after stopping and verify original cohort/variant attribution |
| Cache/performance | Eventual consistency, optional dependency failure, measured bottleneck, and benchmark scope | Change TTL or a measured bottleneck parameter and compare a controlled run |

Explain time/space costs where relevant, bottlenecks, genuine tradeoffs, and a plausible next scaling step. Exact code-level exercises follow the implementation; the completion standard above is settled and is not residual planning fog. Learning gaps can guide follow-up work without fabricated completion claims.

### Finished-project evidence

The project is finished only when the core works end to end and its phase-specific checks have real recorded outcomes. Run relevant backend unit/PostgreSQL integration checks, configured Python lint/type checks, frontend TypeScript/lint/build checks, and the documented Docker/demo verification. Fix correctness/check failures before declaring the affected phase complete.

README and supporting docs must contain the actual setup/run/test/preparation commands, architecture/request-flow diagram, endpoint contracts, recommendation/experiment explanations, tradeoffs/complexity, known limits, and realistic deferred improvements. Include screenshots of the running system and benchmark reports with provenance, including no improvement or incomplete load runs when those occurred.

Use only measured numbers in README/resume claims. Distinguish synthetic behavioral outcomes from real software performance. Preserve count/metric reconciliation, model/index provenance, and the completion/learning evidence needed to explain the system in an interview. No positive lift, ANN promotion, or hardware-independent latency target is required by the definition of done.

### Map completion

All eleven decision tickets are resolved. Public hosting and production retention are explicitly outside this release; specific optimizations depend on measurements during implementation under the settled benchmark procedure. No additional pre-build question or research ticket remains. The next work is Phase 1 implementation using the linked contracts, not another wayfinding ticket.
