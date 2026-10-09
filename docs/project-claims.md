# AdFlow project and interview notes

Use these claims as a compact explanation of the project. All activity, exposures,
clicks and revenue values in this project are synthetic; the application is a local Docker
demo, and its dashboards do not make rollout decisions.

## Project summary

Built a local ad recommendation and experimentation demo with a FastAPI service,
PostgreSQL-backed recommendation/event history, an optional Redis profile cache, offline
retrieval and CTR artifacts, and a read-only React dashboard. The [architecture and
setup guide](../README.md#architecture) describes the service boundaries and Docker flow.

Recommendations are committed with an idempotency key and an immutable selected-ad and
experiment snapshot. Clients confirm impressions before attributed clicks; PostgreSQL
credits the saved bid once. Redis stores bounded profile data and falls back to PostgreSQL
on cache failure. Retrieval uses exact Flat by default, filters current eligibility, and
falls back to an exact current-catalog scan when the configured snapshot cannot safely
serve the request. Offline synthetic history, features, chronological splits, training,
evaluation and bundle packaging use explicit commands.

## Evidence-backed discussion

- **Retrieval decision:** compared Flat and HNSW on the 100,000-ad synthetic catalog with
  30 nonempty queries, three repetitions, candidate limit 500, one FAISS thread and
  `m=32`, `efConstruction=200`, `efSearch=128`. Flat full-retrieval P95 was 40.715 ms.
  The HNSW path including fallback was 6,631.704 ms; mean/minimum tie-aware recall was
  86.667% / 0%. The promotion gate failed, so Flat remains the serving default. See the
  [full measurement and configuration](../.scratch/adflow-implementation/evidence/ticket16/results.md#full-experiment)
  and [ticket 16 decision](../.scratch/adflow-implementation/issues/16-retrieval-benchmarks.md).
- **HTTP workload:** completed a matched 24-configuration smoke matrix at 10 users with
  one repetition, 1-second warm-up, 3-second measurement and 3-second drain. Every run
  completed without request errors, but these checks are too short and sparse to compare
  performance. The separate rapid-ramp checks at 100 and 500 users saturated the one-worker
  service; they establish neither a stable capacity limit nor fixed-rate throughput. See the
  [raw matrix](../artifacts/benchmarks/ticket49-paired-10/flat-disabled-lifecycle-hot-no-cache/20261009T184651Z-2ace7078-461f-4c9c-9721-c2c858e73f5d/matrix.json),
  [run configuration](../artifacts/benchmarks/ticket49-paired-10/flat-disabled-lifecycle-hot-no-cache/20261009T184651Z-2ace7078-461f-4c9c-9721-c2c858e73f5d/lifecycle-users-10-rep-1/configuration.json),
  [run report](../artifacts/benchmarks/ticket49-paired-10/flat-disabled-lifecycle-hot-no-cache/20261009T184651Z-2ace7078-461f-4c9c-9721-c2c858e73f5d/report.md),
  [ticket 49 commands and outputs](../.scratch/adflow-implementation/issues/49-benchmark-matrix.md)
  and [ticket 51's evidence boundaries](../.scratch/adflow-implementation/issues/51-performance-gate.md).
- **Offline model data:** generated independent synthetic historical exposures and
  evaluated a persisted CTR pipeline. These labels are designed outcomes, not real
advertising behavior or evidence that the model improves ranking. The [history report](../.scratch/adflow-implementation/issues/18-synthetic-history.md)
and [CTR evaluation](../.scratch/adflow-implementation/issues/21-ctr-evaluation.md)
preserve their separate source/configuration and evaluation limitations.

No claim is made for a statistically significant experiment winner, production-scale
capacity, public hosting, real-user effectiveness, or a universal latency target.

## Optional resume wording

> Built a Dockerized synthetic ad recommendation demo with durable, idempotent lifecycle
> APIs; exact and approximate retrieval comparisons; a reproducible offline CTR pipeline;
> experiment attribution; optional Redis caching; and a read-only React dashboard. Kept
> Flat retrieval as the default after HNSW failed the measured quality/latency gate.

If adding numbers, copy them from the linked reports with their workload and limitations.
Do not describe simulated click credit as actual revenue or simulated click rates as real
advertising effectiveness.
