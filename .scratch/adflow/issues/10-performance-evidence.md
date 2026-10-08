# What measurements will substantiate the performance claims?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 03, 08

## Question

Define benchmark datasets, hardware/runtime metadata, warmup, request/event workload, concurrency scenarios including 10/100/500 users, duration, errors, and latency/throughput reporting. Decide comparable baselines for retrieval and caching, pipeline timings, load-generator placement, and how to document saturation or incomplete runs. Set practical acceptance criteria without inventing hardware-independent latency promises.

## Comments

The round notes below are chronological history. The final contract is under Answer.

### Confirmed comparison and workload choices

- Nathan accepted separating retrieval and cache comparisons. Compare full-ad ranking, exact retrieval plus ranking, and HNSW retrieval plus ranking with the same strategy/model/dataset; compare cache enabled/disabled with retrieval and ranking fixed. Measure components and full API requests.
- Nathan accepted separate recommendation-only and complete recommendation/impression/possible-click lifecycle workloads. Recommendation-only requests still persist selections; lifecycle requests include event writes. Distinguish endpoint request rates/latencies from completed ad opportunities.
- Nathan accepted attempts at 10/100/500 simulated users, with documented early termination on saturation. Record actual dataset/concurrency/completed requests/failures/stop reason; do not infer capacity from incomplete runs or invent hardware-independent latency targets.
- Run timing/pacing, user locality, measurement scope, telemetry, and completion criteria remain open pending Locust research and discussion.

Claimed at Nathan's request on 2026-10-07. Starting a live discussion of reproducible load scenarios, comparable baselines, latency/throughput/error measurements, telemetry, and honest acceptance criteria. Supporting Locust research will inform tool-specific details.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted continuous closed-loop scenarios without intentional think time, post-ramp 60-second warmup and three-minute measurement, three repetitions for quoted comparisons, uniform/hot-user and cold/warm cache distinctions, a documented single-worker Docker reference, bounded process-local rolling telemetry, and complete latency/error/resource/provenance reporting. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. [HTTP load-test evidence options](../research/load-test-options.md) supplies official-source Locust findings. This is a measurement plan; no benchmark, optimization, or capacity result has been produced.

### Tools and reference environment

Use Locust for Python HTTP workloads and reproducible component scripts for vector search/ranking measurements. Pin and record the actual tool/runtime versions. Initial reference deployment is Docker with one API worker. Record generator placement, CPU/memory, software/OS, Docker limits, API worker/thread settings, database/Redis pools, and FAISS thread settings. Additional workers or a separate generator host constitute separate benchmark configurations.

Colocating generator and services on one machine is acceptable if disclosed. Monitor generator and server resource use; generator saturation is not server capacity. Choose and document the HTTP client, connection reuse, finite timeouts, and retry behavior explicitly. Avoid expensive per-request data generation in the load generator. Do not assume Locust concurrency means RPS or simultaneous network requests.

### Workloads and concurrency

- Recommendation-only: fresh opportunity/request key per iteration; selections still persist normally. Never disable durable writes to obtain an unlabeled faster endpoint result.
- Lifecycle: recommendation, display confirmation, then a possible click from the independent outcome rule. Respect event ordering and preserve keys/IDs for any explicitly tested retry.
- Each simulated user completes a scenario before starting the next, with no intentional think time for concurrency benchmarks. This is closed-loop load: achieved arrival rate can fall as responses slow. It does not prove a fixed externally offered request rate.
- Attempt 10, 100, and 500 simulated-user scenarios. Distinct synthetic profile count and Locust user count are separate parameters. Record requested and achieved concurrency.
- Keep normal throughput scenarios distinct from intentional replay/fault tests and from the fixed-rate demo simulator.
- Report HTTP requests/second by endpoint and new/completed ad opportunities/second separately. A lifecycle makes multiple calls per opportunity; its total HTTP count is not recommendation throughput.

Use reproducible uniform profile selection across the declared dataset and a separate explicitly configured hot-user workload. Preserve identical sequences/distribution, click rules, and seeds for paired comparisons. Report the hot-set size and sampling policy; do not report a high-locality cache result as universal traffic behavior.

### Comparable baselines

Compare full-ad ranking, exact retrieval plus ranking, and HNSW retrieval plus ranking on the same dataset, user-query set, ranking strategy/model, eligibility snapshot, and hardware. Record candidate counts, score/winner differences, and the existing tie-aware recall/HNSW promotion gate. Full-ad ranking is a benchmark configuration, not a production query flag exposed to arbitrary clients.

Compare Redis enabled versus disabled with retrieval/ranking and all other relevant settings fixed. Separate cold-start/cache-reset results from warmed-cache steady state. Keep cache reset, database preparation, index/model loading, and event-table initial state explicit; do not reset development data or silently erase unrelated records.

Use the small dataset for smoke tests and the optional full 100,000-ad dataset for claims about that scale. Record actual entity/history counts and manifest IDs. Attempted but incomplete comparisons remain incomplete. Dataset generation and offline training are outside timed serving unless specifically labeled as build/training measurements.

### Timing, repetition, and drain

For reported steady-state runs: ramp to target users, then warm up for 60 seconds at target, then measure for three minutes. Exclude ramp/warmup from reported statistics. Run three independent repetitions for quoted comparative improvements; retain each result and variation instead of selecting only the best. Shorter development smoke tests remain labeled as such.

Use explicit phase timestamps and verify tool statistics reset at the measurement boundary. Locust's run-time includes ramp, and its reset-on-spawn option alone does not implement the agreed post-ramp warmup. Statistics reset does not reset cache/database state.

Drain in-flight lifecycles with a documented finite timeout; report any interrupted/unfinished opportunities. Keep measurement-window request/operation classification consistent around boundaries and do not silently include warmup or drain samples. Preserve request timestamps/phase labels sufficient to explain the chosen accounting.

### Measurements and exports

Record client-observed HTTP latency separately from server total request time and component times: user/profile lookup, vector search, metadata/filtering/backfill, feature generation, CTR batch prediction, ranking/selection, and durable database logging/commit. A complete lifecycle timer includes multiple calls and simulator work; label it separately.

Report mean/P50/P95/P99 and counts for successful new selections, with distinct replay, no-ad, failed-request, and event-endpoint populations. Report transport errors, timeouts, HTTP failures, semantic response failures, achieved rates, fallback/cache metrics, CPU/memory, and database/resource symptoms. Validate response bodies rather than equating every 2xx response with a valid recommendation.

Retain resolved configuration, run ID, application revision/snapshot identity, dataset/generator/model/index/feature versions, seeds, workload distribution, spawn schedule, cache state, timestamps, actual users/counts, logs, and raw tool exports. CSV/HTML summaries and histories are tool outputs, not necessarily raw per-request samples. State histogram rounding/percentile approximation and window scope for the pinned version. Never average interval or repetition P95s and call the result a combined percentile; preserve per-run values or combine underlying compatible distributions.

For a quoted latency improvement, identify the exact baseline/configuration/population and use measured values. If baseline is unavailable or zero, do not fabricate a percentage. Report throughput/errors/quality alongside latency so a faster failure path or poorer retrieval cannot masquerade as an improvement.

### Live dashboard telemetry

Initially use bounded process-local rolling telemetry for the agreed 15-minute performance view. Include request outcome population, monotonic duration measurements, actual time coverage, process/start identity, retained sample counts, and truncation/dropped-sample information. A configured count/memory cap may shorten coverage under load; disclose it instead of claiming a full 15-minute sample.

Live counters/histograms must still distinguish cache misses/errors/bypasses and experiment failures. Restarts reset this telemetry; persistent recommendation/event records remain authoritative for business counts. Global multi-worker telemetry and a monitoring platform are deferred. Do not sum/average process percentiles as if they represented a complete global distribution.

Saved benchmark outputs are independent of this buffer. Benchmark and live-dashboard numbers have different windows and scopes, and neither should silently replace the other. Instrumentation has a cost; keep it fixed during paired comparisons and record configuration.

### Saturation, completion, and claims

Allow documented early termination for resource exhaustion, generator saturation, failure to reach concurrency, excessive errors, or interrupted/incomplete measurement. Record the stop reason, actual phase duration, counts, resource evidence, and achieved rates. A failed/incomplete 500-user run is a limitation, not a successful 500-user capacity claim.

Completion requires runnable documented scenarios, trustworthy phase/outcome classification, retained provenance/exports, component/API comparisons, and honest reports of attempted scale and failures. Verify stats boundaries, count reconciliation, semantic response checks, telemetry truncation/reset, and endpoint/opportunity separation. No universal latency, throughput, zero-error, or speedup threshold is invented here; correctness requirements still apply independently of saturation.

Optimize only after profiling identifies a bottleneck. Rerun affected comparable scenarios after changes, and publish regressions or lack of improvement. Concrete optimization implementation depends on real measurements during the build; this map defines the evidence procedure rather than guessing those changes now. No additional pre-build decision ticket is required.
