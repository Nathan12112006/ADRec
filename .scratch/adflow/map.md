# AdFlow — Full-project decision map

Labels: wayfinder:map
Status: resolved
Completed: 2026-10-07 (planning only)

## Destination

Agree on a build-ready scope, contracts, architecture, and staged acceptance plan for the complete AdFlow portfolio project, starting with a working Phase 1 backend. The route is clear when no required design decisions remain before implementation; this map does not build the application.

## Notes

- [Original project brief](brief.md) is source material. Confirmed scope choices in these Notes take precedence over its broader feature list and immediate-build instructions for this planning effort.
- Owner: Nathan. Consult the wayfinder, grilling, and domain-modeling skills in each decision session. Use research or prototype when a ticket requires them.
- This is a planning effort. Charting resolves no human decision tickets. Work one decision ticket per later session, except research.
- Confirmed scope: FastAPI, PostgreSQL, configurable synthetic data, FAISS retrieval, Logistic Regression CTR prediction, two ranking strategies, deterministic A/B experiments with correct event attribution, Redis with fallback, a compact React dashboard, Docker, meaningful tests, reproducible benchmarks, and interview explanations.
- Optimize for the quickest credible completion; no deadline. Cut features where needed to protect this core.
- Include a reproducible simulator that generates requests and synthetic clicks so a reviewer can watch experiment results develop. Distinguish synthetic outcomes from measured system performance.
- Advertising economics are simulated. No real payments or budget enforcement in the initial scope; the lifecycle ticket holds the agreed accounting contract.
- The dashboard decision defers conversions and advertiser reporting beyond the core. Ranking defers blended scoring/auction pricing; experimentation defers significance testing and overlapping experiments.
- The delivery decision fixes this release at a reproducible Docker demo; public hosting is a separate follow-up.
- Preserve preferred stack unless a strong technical reason warrants a change. Verify version/platform facts against primary sources when they become necessary.
- Implementation must be incremental, with Phase 1 verified before Phase 2. Explain major choices, complexity where relevant, bottlenecks, tradeoffs, and scaling options; include hands-on learning checkpoints.
- Repository inspection found only agent instructions, no application code or existing planning, and no Git repository.
- Local tracker: children live in issues/. Type and Labels identify wayfinder ticket types. Status: needs-info means open and unclaimed; Status: claimed means in progress; Status: resolved means closed. Claim before work. Blocked by lists sibling ticket numbers; empty means no dependencies.
- Resolve by recording the answer under ## Answer, setting Status: resolved, and adding a named link with a one-line gist below. Refer to issues by title in user-facing discussion.
- Find the frontier by scanning open, unclaimed children whose dependencies are resolved; choose the lowest number. Do not rely on a static frontier list.

## Decisions so far

- [What constitutes a served ad and a valid attributed click?](issues/01-serving-and-events.md#answer) — Client-confirmed impressions, recommendation-based attribution, safe retries, a 24-hour event window, and captured-bid simulated revenue.
- [What is the smallest reliable Phase 1 backend?](issues/02-phase-one-boundary.md#answer) — Modular FastAPI/PostgreSQL backend, complete event lifecycle, deterministic scan baseline, small seeds, migrations, and tested local/Docker completion gates.
- [How will synthetic data and simulated traffic provide honest evidence?](issues/03-synthetic-world.md#answer) — Reproducible independent click simulation, randomized history with temporal splits, and API-driven live traffic kept separate from training artifacts.
- [What retrieval contract makes FAISS useful and measurable?](issues/04-candidate-retrieval.md#answer) — Cosine topic retrieval with eligible top-500 candidates, immutable snapshots and exact fallback, plus measured Flat/HNSW quality and latency gates.
- [What CTR model and evaluation contract are credible for synthetic data?](issues/05-ctr-evaluation.md#answer) — Shared offline-trained Logistic Regression pipeline, probability metrics against a base-rate baseline, versioned batch serving, and explicit 503 on CTR-model failure.
- [How will two ranking strategies choose winners without redundant scoring?](issues/06-ranking-economics.md#answer) — V1 overlap and V2 CTR-times-bid select directly with deterministic ties, shared retrieval, and captured-bid accounting.
- [What experiment contract makes comparisons interpretable?](issues/07-experiment-contract.md#answer) — Stable user assignment and immutable single experiments, preserved late attribution, explicit exposed-user metrics, visible failures, and descriptive reporting.
- [What should Redis cache and how will dependency failures behave?](issues/08-cache-and-failures.md#answer) — Profile-only cache-aside with versioned keys, 60-second maximum TTL, bounded Redis waits, PostgreSQL fallback, and visible failure/health metrics.
- [What is the smallest dashboard that demonstrates the complete system?](issues/09-dashboard-demo.md#answer) — Read-only Overview/Experiments/Performance views, backend summaries, explicit windows, five-second polling, and honest stale/unavailable states.
- [What measurements will substantiate the performance claims?](issues/10-performance-evidence.md#answer) — Comparable retrieval/cache workloads, 10/100/500-user attempts, explicit warmup/repeats, scoped telemetry, and retained evidence without promised speedups.
- [What staged delivery plan proves completion and interview readiness?](issues/11-delivery-and-learning.md#answer) — Nine verified implementation phases, explicit reviewer preparation, Docker-only release, retained history, and explain-and-modify checkpoints.

## Not yet specified

None. All required pre-build decisions are resolved. The [implementation handoff](spec.md) points to the canonical answers and first phase. Implementation-time verification, profiling, and learning exercises follow the settled delivery/benchmark procedures.

## Out of scope

- Application implementation during this planning effort; hand off the agreed route for staged execution.
- Real user data, real advertising payments, and initial budget enforcement.
- Advanced distributed infrastructure, streaming pipelines, feature stores, neural ranking, and Ranking V3.
- Blended scoring and auction pricing — deferred to keep the core small; see [How will two ranking strategies choose winners without redundant scoring?](issues/06-ranking-economics.md#answer) for the chosen selection contract.
- Significance testing, automatic winner/rollout decisions, overlapping experiments, and audience targeting — deferred by [What experiment contract makes comparisons interpretable?](issues/07-experiment-contract.md#answer).
- Live profile-edit APIs and broader/distributed cache infrastructure — deferred by [What should Redis cache and how will dependency failures behave?](issues/08-cache-and-failures.md#answer).
- Advertiser reporting, conversion tracking/views, and browser-based simulator/experiment controls — deferred by [What is the smallest dashboard that demonstrates the complete system?](issues/09-dashboard-demo.md#answer).
- Global multi-worker telemetry and an additional monitoring platform — deferred by [What measurements will substantiate the performance claims?](issues/10-performance-evidence.md#answer).
- Public hosting and production retention/archival policy — separate follow-up work under [What staged delivery plan proves completion and interview readiness?](issues/11-delivery-and-learning.md#answer).
- Fabricated performance improvements or claims that synthetic outcomes demonstrate real-world ad effectiveness.
