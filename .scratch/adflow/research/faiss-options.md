# FAISS options for AdFlow candidate retrieval

Research date: 2026-10-07. Supports [ticket 04](../issues/04-candidate-retrieval.md); these are findings and recommendations, not resolved product decisions. No benchmarks or installation tests were performed. Upstream `main` and wiki pages can change; pin an implementation release and recheck its APIs.

## Conclusion

Start with CPU `IndexFlatIP` as the exact reference and simplest serving implementation. Compare one CPU `IndexHNSWFlat` alternative using the same normalized vectors and eligibility snapshot. Retain Flat if approximation offers no useful measured benefit. Defer IVF and compression. This is an engineering recommendation, not a performance claim.

The proposed full dataset has 100,000 ads and a vocabulary of only 13 interest topics. If represented as binary topic membership, there are at most 8,191 nonempty distinct vectors (a mathematical inference: `2^13 - 1`), so duplicates and similarity ties are unavoidable at that size. Do not add arbitrary random dimensions to manufacture an ANN win. FAISS's FAQ cautions that low-dimensional search is not its strongest use case and that duplicate/near-duplicate vectors can hurt both IVF and HNSW. It also documents arbitrary ordering among tied distances. [Official FAQ](https://github.com/facebookresearch/faiss/wiki/FAQ)

## Source facts

### Similarity and empty interests

For cosine similarity, normalize both stored vectors and query vectors to unit length and use inner-product search; inner product alone is not cosine. Higher scores are better. For unit vectors, squared L2 distance equals `2 - 2 * inner_product`. [Metrics documentation](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)

The normalization implementation divides only when the squared norm is positive, leaving a zero vector unchanged. Zero-vector cosine is mathematically undefined; an all-zero inner-product query instead gives every vector score zero. [Normalization source](https://github.com/facebookresearch/faiss/blob/main/faiss/utils/distances.cpp)

Recommendation: treat empty-interest users explicitly through a documented nonpersonalized eligible-ad fallback; reject or quarantine zero-interest ads at generation/index build unless a separate fallback policy includes them. Validate vocabulary, dimension, finite values, dtype, and normalization before indexing. Binary membership vectors keep the first implementation explainable; changing to weighted interests changes retrieval semantics and needs a vector-version change.

### Flat, HNSW, and IVF

| Option | Source-supported behavior | AdFlow implication |
| --- | --- | --- |
| `IndexFlatIP` | Exhaustive exact search; stores `4*d` bytes per vector. | Reference and credible serving choice. Raw vectors alone at `100000*13*4` occupy 5,200,000 bytes, excluding IDs, process overhead, metadata, and build copies. |
| `IndexHNSWFlat` | Nonexhaustive graph search with uncompressed vectors and extra graph storage. | Smallest ANN comparison; more memory/build cost can outweigh savings here. |
| `IndexIVFFlat` | Trained cell partitioning; searches `nprobe` of `nlist` lists with full-vector scoring in visited lists. Stores vector data plus IDs. | Adds training and partition tuning; duplicate-heavy vectors may create imbalanced lists. Defer unless measurements justify it. |

These method descriptions and storage formulas come from [FAISS indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes). The raw-memory arithmetic and project implications are our inferences. Flat is still a scan; reducing expensive downstream ranking from all ads to 500 candidates can help even when retrieval itself is exhaustive. Compare that benefit separately from ANN search savings.

HNSW requires no training. `M` controls graph connectivity and memory; `efSearch` controls the speed/accuracy tradeoff. HNSW supports sequential addition, needs an ID map wrapper for supplied IDs, and does not support vector removal. Flat also needs an ID map for supplied IDs. [Index selection guidance](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)

Recommendation: keep a stable int64 FAISS ID to database ad ID mapping in the index artifact (or use `IndexIDMap2` after verifying the pinned release). Never interpret transient result positions as database IDs. UUID/text database IDs require a separate mapping. For a minimal comparison use one declared HNSW build configuration and sweep several `efSearch` settings appropriate to a top-500 query; record all settings rather than claiming defaults are optimal.

### Filtering and freshness

Search parameters can carry an `IDSelector` identifying acceptable IDs. A Python callback selector is inefficient because it calls Python while capturing the GIL. [Per-query search parameters](https://github.com/facebookresearch/faiss/wiki/Setting-search-parameters-for-one-query)

Current HNSW source supports selectors: it checks whether a visited node may enter results while graph traversal can still visit rejected nodes. Thus it is wrong to say HNSW cannot filter at all; filtering does not physically remove graph nodes or guarantee finding every eligible neighbor. Wrapper and release behavior must be tested. [HNSW implementation](https://github.com/facebookresearch/faiss/blob/main/faiss/impl/HNSW.cpp)

Recommendation: build from active ads belonging to active advertisers; batch-fetch current metadata from PostgreSQL and recheck eligibility before recording a recommendation. Retrieve more results when eligibility filtering shrinks the pool. Cap ANN expansion and use a measured exact eligible scan if fewer than `min(500, eligible_count)` remain. Keep fallback counts visible so fallback does not masquerade as ANN speed. ANN may miss better candidates even when it returns 500, so filling the count is not an exactness guarantee. A fresh eligibility query cannot recover a newly added vector absent from a stale index; use a catalog/vector version and reject incompatible snapshots or explicitly document delayed visibility.

## Persistence and rebuilds

FAISS provides `write_index` and `read_index`. Its loader should receive trusted verified artifacts because it does not fully validate loaded data. [Index I/O](https://github.com/facebookresearch/faiss/wiki/Index-IO,-cloning-and-hyper-parameter-tuning)

CPU searches may run concurrently, but concurrent search/add and add/add require application locking. [Concurrency FAQ](https://github.com/facebookresearch/faiss/wiki/FAQ)

Recommendation: build a replacement immutable index off the serving path, validate it, persist it with a manifest, and swap a process-local reference under a brief lock. In-flight requests retain the old reference. Avoid mutating the live index. Manifest fields: FAISS version/build, vector schema and vocabulary order, normalization/metric, catalog version, row count, ID-map checksum, build seed/settings, and creation time. Multi-worker processes each load a complete version; filesystem publication and worker reload must be explicit. Rebuild in the destination runtime rather than promising arbitrary binary portability. Missing, corrupt, incompatible, or overly stale artifacts use the exact eligible scan and report the degraded mode.

## Honest recall and latency comparison

Recommendation:

1. Freeze one catalog/eligibility snapshot and one held-out reproducible query set. Record repeated-vector counts and empty-interest frequency. Benchmark nonempty queries and fallback queries separately.
2. Compare all-ad ranking, Flat retrieval plus ranking, and HNSW retrieval plus the same ranking. Separate vector search timing from metadata lookup, filtering/backfill, ranking, persistence, and HTTP latency.
3. Report build time, artifact size, process memory, query p50/p95/p99, throughput, requested/returned candidate counts, and fallback rate. Fix hardware, runtime, threads, warmup, batching, concurrency, and settings. Report single-query latency separately from batch throughput.
4. Report ordinary ID-intersection recall@500 against an exact result set, but label its tie sensitivity. Add a tie-aware score metric against all exact eligible scores: let `k=min(500, eligible_count)`, boundary score `t`, `G` be eligible IDs scoring above `t` beyond the declared tolerance, `T` the boundary-tied IDs, and `R` the unique eligible retrieved IDs (at most `k`). Use `(size(R intersect G) + min(size(R intersect T), k-size(G))) / k`; report missed strictly-better IDs separately. Return no recall value for `k=0`. This prevents rewarding a full pool of boundary ties while omitting superior candidates.
5. Sorting only the 500 returned IDs cannot enforce a global ad-ID tie-break over a larger tied boundary. If global deterministic membership is required, exact boundary expansion or complete exact scoring is necessary; otherwise explicitly permit any tied boundary members. Fix the tolerance before measuring.
6. Measure downstream winner agreement and ranking-score loss separately. Good similarity recall does not guarantee retaining the ad with the best CTR prediction or bid-based score. Accept no speedup, worse recall, or no downstream improvement as honest outcomes.

These are proposed measurement rules. No empirical result is asserted. FAISS supports tuning against ground truth and identifies recall/search-time operating points, but the tie-aware metric above is an AdFlow-specific proposal. [Official tuning documentation](https://github.com/facebookresearch/faiss/wiki/Index-IO,-cloning-and-hyper-parameter-tuning)

## Current installation and portability

Do not rely on old claims that pip distributions are exclusively community-maintained. The current upstream release history includes PyPI publication work, and the current `faiss-cpu` PyPI project identifies Meta AI Research with a `facebook` maintainer. As checked on this date, release 1.15.1 lists Python >=3.10, Windows x86-64 wheels for CPython 3.10 through 3.14, and Linux x86-64/aarch64 wheels with specific platform tags. A wheel existing does not prove it will run in this workspace. [Upstream release](https://github.com/facebookresearch/faiss/releases/tag/v1.14.2), [Current package and wheel files](https://pypi.org/project/faiss-cpu/)

The current upstream INSTALL still documents conda as its supported installation route and lists CPU packages for Linux, macOS ARM, and Windows x86-64. This wording is inconsistent with newer packaging evidence, so preserve both facts instead of repeating the older wiki's blanket pip caveat. [Upstream INSTALL](https://github.com/facebookresearch/faiss/blob/main/INSTALL.md)

Recommendation: pin CPU-only FAISS, NumPy, Python, and a Linux Docker base image after a smoke test of normalized search, IDs, persistence, and reload. Test Windows development separately against its actual Python/architecture tags. Use Linux Docker as the reproducible reference environment; native Windows is feasible rather than guaranteed. No GPU dependency or source compilation is needed merely to demonstrate this dataset.
