# AdFlow implementation backlog

Status: ready-for-agent
State: open

This backlog turns the accepted [implementation handoff](../adflow/spec.md) into 64 execution tickets across nine phases: 47 implementation tasks, nine technical verification gates, seven human checkpoints, and one final release reconciliation ticket. Application code and measured evidence are not yet complete.

## Authority and scope

The [resolved decision map](../adflow/map.md), linked answers below and [root domain language](../../CONTEXT.md) govern this work. Tickets decompose those contracts rather than replace them. If a ticket summary omits an edge case, follow the owning resolved answer.

Deliver the Docker demo in phase order. Public hosting, conversions, advertiser reporting, auction pricing, statistical winner/rollout automation, overlapping experiments, browser administration, live profile-edit APIs, production retention policy and advanced distributed infrastructure remain outside this release. Keep durable history; resets target explicitly isolated test/benchmark databases.

## Execution and evidence

`Status` uses the repository's triage roles: `ready-for-agent` routes technical work and `ready-for-human` routes Nathan's checkpoints. It does not mean dependencies are satisfied. The separate `State` field records execution: `open`, `active`, or `done`. These are implementation tickets, separate from the resolved wayfinding tickets.

Dependencies in `Blocked by` refer only to IDs in this backlog. A dependency is satisfied when its ticket has `State: done`. Select the lowest-numbered open agent ticket whose dependencies are done, set its state active and assign it before work, then record results under Comments and mark done only after its acceptance criteria pass. If information is missing, use `needs-info` and explain the gap; do not mark blocked work complete. The initial eligible ticket is [01 — Create the backend package and configuration foundation](issues/01-backend-foundation.md).

Complete each phase's technical gate before starting the next phase. Preserve focused working changes. Every technical ticket includes relevant tests/checks and current setup documentation as part of its scope even where not repeated. Follow canonical unit/PostgreSQL integration, Python lint/type, frontend TypeScript/lint/build and Docker checks appropriate to the change. Recheck version-sensitive dependencies against primary sources during implementation.

Record actual files/changes, exact commands, results, artifact/configuration identity and limitations under Comments. Explain relevant complexity and tradeoffs. Never fabricate successful checks, model quality, runtime compatibility, benchmark improvements or completed learning. Check failures must be fixed before declaring the affected phase complete. Performance improvements and HNSW promotion are conditional on measured evidence; no positive lift or universal speed target is required.

Offer each explain-and-modify checkpoint after its component gate. Human checkpoints remain separately routed so technical dependencies are explicit; completing an agent gate never certifies Nathan's understanding. Record his actual explanation/change/checks and gaps. The final release ticket depends on both the technical gate and human review. If a checkpoint change alters code, rerun the affected checks and update its gate evidence.

## Phase gates

| Phase | Technical gate | Required before next phase |
| --- | --- | --- |
| 1 — Core backend | [10 — Verify and record the Phase 1 completion gate](issues/10-phase-one-gate.md) | Recorded passing phase checks and evidence |
| 2 — Candidate retrieval | [17 — Verify and record the candidate-retrieval phase gate](issues/17-retrieval-gate.md) | Recorded passing phase checks and evidence |
| 3 — CTR model | [23 — Verify and record the CTR-model phase gate](issues/23-ctr-gate.md) | Recorded passing phase checks and evidence |
| 4 — Ranking and selection | [26 — Verify and record the ranking phase gate](issues/26-ranking-gate.md) | Recorded passing phase checks and evidence |
| 5 — Experiments | [33 — Verify and record the experimentation phase gate](issues/33-experiments-gate.md) | Recorded passing phase checks and evidence |
| 6 — Redis | [38 — Verify and record the Redis phase gate](issues/38-cache-gate.md) | Recorded passing phase checks and evidence |
| 7 — Dashboard | [45 — Verify and record the dashboard phase gate](issues/45-dashboard-gate.md) | Recorded passing phase checks and evidence |
| 8 — Load testing and optimization | [51 — Verify and record the performance evidence phase gate](issues/51-performance-gate.md) | Recorded passing phase checks and evidence |
| 9 — Final polish | [56 — Record the final technical delivery gate](issues/56-final-technical-gate.md) | Technical delivery record; human review remains separate |

## Ticket index

### Phase 1 — Core backend

- [01 — Create the backend package and configuration foundation](issues/01-backend-foundation.md)
- [02 — Implement PostgreSQL sessions and initial schema migrations](issues/02-postgres-schema.md)
- [03 — Generate reproducible configurable entity seeds](issues/03-small-data-seed.md)
- [04 — Implement deterministic interest-overlap selection](issues/04-baseline-selector.md)
- [05 — Persist recommendations and idempotent request outcomes](issues/05-recommendation-workflow.md)
- [06 — Record client impressions and clicks with atomic accounting](issues/06-event-workflow.md)
- [07 — Expose lifecycle APIs with health checks and structured errors](issues/07-http-health-logging.md)
- [08 — Verify lifecycle races, expiration and dependency failures](issues/08-lifecycle-integration-tests.md)
- [09 — Package the backend and document Phase 1 setup](issues/09-backend-docker-setup.md)
- [10 — Verify and record the Phase 1 completion gate](issues/10-phase-one-gate.md) — verification gate

### Phase 2 — Candidate retrieval

- [11 — Define versioned topic vectors and the retrieval result contract](issues/11-topic-vectors.md)
- [12 — Build and reload exact FAISS index snapshots](issues/12-flat-index-artifacts.md)
- [13 — Implement current eligibility filtering and exact fallback](issues/13-eligibility-backfill.md)
- [14 — Add the HNSW candidate-retrieval comparison](issues/14-hnsw-option.md)
- [15 — Integrate candidate retrieval into recommendation serving](issues/15-retrieval-serving.md)
- [16 — Measure exact and approximate retrieval quality and cost](issues/16-retrieval-benchmarks.md)
- [17 — Verify and record the candidate-retrieval phase gate](issues/17-retrieval-gate.md) — verification gate

### Phase 3 — CTR model

- [18 — Generate independent historical exposure and click outcomes](issues/18-synthetic-history.md)
- [19 — Build shared CTR features and chronological splits](issues/19-features-splits.md)
- [20 — Train a persisted preprocessing and Logistic Regression pipeline](issues/20-logistic-training.md)
- [21 — Evaluate CTR probabilities against the training base-rate baseline](issues/21-ctr-evaluation.md)
- [22 — Load validated model artifacts and predict candidate batches](issues/22-ctr-artifact-serving.md)
- [23 — Verify and record the CTR-model phase gate](issues/23-ctr-gate.md) — verification gate

### Phase 4 — Ranking and selection

- [24 — Implement interchangeable V1 and V2 ranking strategies](issues/24-ranking-strategies.md)
- [25 — Persist coherent ranked selections and explicit response context](issues/25-ranked-selection-context.md)
- [26 — Verify and record the ranking phase gate](issues/26-ranking-gate.md) — verification gate

### Phase 5 — Experiments

- [27 — Persist experiments and stable synthetic-user assignment](issues/27-experiment-schema-assignment.md)
- [28 — Expose validated experiment create/start/stop/list APIs](issues/28-experiment-management.md)
- [29 — Route recommendations with immutable experiment attribution](issues/29-experiment-routing.md)
- [30 — Collect bounded rolling request and pipeline telemetry](issues/30-rolling-telemetry.md)
- [31 — Implement cohort-based experiment result aggregates](issues/31-experiment-results.md)
- [32 — Build reproducible API-driven demo traffic and edge scenarios](issues/32-live-simulator.md)
- [33 — Verify and record the experimentation phase gate](issues/33-experiments-gate.md) — verification gate

### Phase 6 — Redis

- [34 — Implement bounded Redis profile-cache access](issues/34-profile-cache-adapter.md)
- [35 — Integrate cache fallback and post-commit invalidation](issues/35-cache-serving-invalidation.md)
- [36 — Expose dependency capabilities and disposable Redis configuration](issues/36-cache-health-operations.md)
- [37 — Measure profile-cache behavior under reproducible access patterns](issues/37-cache-comparison.md)
- [38 — Verify and record the Redis phase gate](issues/38-cache-gate.md) — verification gate

### Phase 7 — Dashboard

- [39 — Expose overview and performance summary APIs](issues/39-dashboard-read-apis.md)
- [40 — Create the React dashboard shell and reliable polling](issues/40-frontend-foundation.md)
- [41 — Build the live overview dashboard](issues/41-overview-dashboard.md)
- [42 — Build experiment list and comparison detail views](issues/42-experiment-dashboard.md)
- [43 — Build the rolling performance and dependency view](issues/43-performance-dashboard.md)
- [44 — Package and verify the complete read-only dashboard](issues/44-frontend-packaging.md)
- [45 — Verify and record the dashboard phase gate](issues/45-dashboard-gate.md) — verification gate

### Phase 8 — Load testing and optimization

- [46 — Implement reproducible Locust benchmark workloads](issues/46-locust-workloads.md)
- [47 — Build controlled benchmark execution and provenance capture](issues/47-benchmark-runner.md)
- [48 — Produce honest latency and workload reports](issues/48-benchmark-reporting.md)
- [49 — Execute the controlled performance comparison matrix](issues/49-benchmark-matrix.md)
- [50 — Profile measured bottlenecks and verify justified improvements](issues/50-profile-measured-bottlenecks.md)
- [51 — Verify and record the performance evidence phase gate](issues/51-performance-gate.md) — verification gate

### Phase 9 — Final polish

- [52 — Verify explicit artifact preparation and fresh Docker startup](issues/52-fresh-setup-walkthrough.md)
- [53 — Finish reviewer documentation, diagrams and real screenshots](issues/53-readme-reviewer-evidence.md)
- [54 — Run final correctness and build verification](issues/54-final-regression.md)
- [55 — Audit project and resume claims against measured evidence](issues/55-claims-evidence-audit.md)
- [56 — Record the final technical delivery gate](issues/56-final-technical-gate.md) — verification gate

### Human explain-and-modify checkpoints

- [57 — Explain and modify lifecycle transactions](issues/57-learning-lifecycle.md)
- [58 — Explain and modify retrieval and eligibility](issues/58-learning-retrieval.md)
- [59 — Explain and modify the CTR pipeline](issues/59-learning-ctr.md)
- [60 — Explain and modify ranking economics](issues/60-learning-ranking.md)
- [61 — Explain and modify experiment attribution](issues/61-learning-experiments.md)
- [62 — Explain and modify caching and performance measurement](issues/62-learning-cache-performance.md)
- [63 — Complete the final explain-and-modify project review](issues/63-final-interview-review.md)

### Final completion

- [64 — Record complete project delivery after human review](issues/64-release-completion.md)

## Canonical contracts

- [Serving and event lifecycle](../adflow/issues/01-serving-and-events.md#answer)
- [Phase 1 backend boundary](../adflow/issues/02-phase-one-boundary.md#answer)
- [Synthetic data and traffic](../adflow/issues/03-synthetic-world.md#answer)
- [Candidate retrieval](../adflow/issues/04-candidate-retrieval.md#answer)
- [CTR model and evaluation](../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../adflow/issues/06-ranking-economics.md#answer)
- [Experiment contract](../adflow/issues/07-experiment-contract.md#answer)
- [Redis and dependency failures](../adflow/issues/08-cache-and-failures.md#answer)
- [Dashboard demo](../adflow/issues/09-dashboard-demo.md#answer)
- [Performance evidence](../adflow/issues/10-performance-evidence.md#answer)
- [Delivery and learning](../adflow/issues/11-delivery-and-learning.md#answer)

Supporting [research pointers](../adflow/spec.md#research-pointers) are planning inputs, not proof of installation or measured performance.

## Comments

Created on 2026-10-07 at Nathan's request to turn all implementation steps into tickets. Existing planning answers remain resolved and unchanged. All execution tickets begin open; this action creates the backlog only.
