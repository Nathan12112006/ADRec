# What retrieval contract makes FAISS useful and measurable?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 02

## Question

Decide user/ad vector construction, similarity definition, approximate index choice criteria, top-500 semantics, ad/advertiser eligibility, filtering and backfill, empty-interest users, index persistence and rebuilds, and metadata lookup. Define recall/latency comparisons and the fallback for a missing or stale index. Decide which baseline is needed to demonstrate why retrieval helps instead of scanning and ranking every ad.

## Comments

The round notes below are chronological history. The final decision is under Answer.

### Confirmed similarity, index, and freshness choices

- Nathan accepted binary topic vectors with cosine similarity; an ad's category is included in its topic membership without extra weighting, and nonempty vectors are normalized.
- Nathan accepted exact IndexFlatIP as the initial default and an IndexHNSWFlat comparison; defer IVF, compression, and GPU support.
- Recheck current ad/advertiser eligibility in PostgreSQL, expand retrieval to a configured bound when filtering shrinks results, then fall back to exact search over current eligible inventory when needed. Report fallback use separately.
- Nathan accepted immutable index snapshots, persisted ID mapping/manifests, validation before swaps, and exact eligible-inventory fallback for missing/corrupt/incompatible or stale snapshots. Catalog changes mark snapshots stale until rebuilt.
- Nathan accepted arbitrary members tied at the candidate boundary, with consistent ordering of returned candidates and explicit tie-aware evaluation rather than a global membership guarantee.
- Primary-source findings: [FAISS options for AdFlow](../research/faiss-options.md). Research is supporting evidence, not an additional resolved ticket.
- Retrieval interface, measurement criteria, and completion checks remain open.

### Confirmed retrieval requirements

- Nathan accepted interpretable user/ad vectors with one dimension per topic in the project vocabulary, encoding user interests and ad interests/category. Bids stay out of retrieval similarity; no artificial dimensions solely to justify approximate search.
- Candidate limit is an upper bound: at most 500 distinct eligible ads, possibly fewer when inventory is limited. Inactive ads and ads from inactive advertisers must not fill the count.
- Users without interests use a fallback of up to 500 eligible ads ordered by bid and then ad ID, marked as fallback retrieval.
- Nathan accepted an exact reference and approximate option, with quality/latency measurements determining the default. Report honestly if exact search is faster; no improvement is presumed.
- Index family, filtering/backfill, lifecycle, and measurement details remain open pending primary-source research and discussion.

Claimed at Nathan's request on 2026-10-07. Beginning a live retrieval-contract discussion; primary-source FAISS research will inform index and implementation choices.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted a candidate/diagnostic retrieval result, configurable limit defaulting to 500, the measured HNSW promotion gate, and all Phase 2 completion checks. This resolution does not claim that any index was built or benchmark passed.

## Answer

Resolved with Nathan on 2026-10-07. Supporting facts and their primary sources are in [FAISS options for AdFlow](../research/faiss-options.md). That note distinguishes library capabilities from project recommendations; this answer records the agreed contract.

### Vectors and similarity

- Use one binary membership dimension per topic in the versioned interest vocabulary. A user vector includes the user's interests; an ad vector includes the union of its interests and category, without double counting or extra category weight.
- Normalize nonempty vectors and use inner product to implement cosine similarity. Higher similarity is better. Bids are excluded from retrieval vectors; later ranking considers bid and CTR where applicable.
- Validate vocabulary order, vector dimensions, finite values, and normalization. Catalog ads need valid category/topic data; invalid zero-vector entries are data validation errors, not arbitrary cosine matches.
- Empty-interest users bypass vector search and receive up to the limit of eligible ads ordered by descending bid, then ascending ad ID. Mark this as nonpersonalized fallback; do not claim a cosine score for its ordering.
- Do not pad vectors with random dimensions to manufacture an approximate-search benefit. Duplicate topic combinations and similarity ties are expected in this synthetic world.

### Retrieval interface and eligibility

Provide a replaceable CandidateRetriever interface with retrieve(user, limit=500) returning a structured result. Ranking, not retrieval, selects the winner.

Each candidate carries its stable ad ID, similarity when applicable, and current metadata needed by ranking. The result carries retrieval mode, index version when applicable, requested and returned counts, retrieval latency, and fallback reason. Keep candidate limit configurable and validate it as a positive bounded setting. Return at most the requested number of distinct eligible ads; small inventories may return fewer.

Build indexes from active ads belonging to active advertisers. Batch-fetch current metadata from PostgreSQL and recheck eligibility; missing/inactive records cannot be ranked merely because their vectors remain in the index. Preserve the lifecycle ticket's requirement that the selected ad be eligible at selection, including changes between candidate retrieval and recommendation recording.

If filtering leaves too few candidates, expand search up to a configured bound, then use an exact search over current eligible inventory if needed. The fallback may scan/score all eligible vectors for retrieval, but still returns at most the limit for downstream ranking. Report its work and fallback mode; never hide it within nominal ANN latency. No eligible ads follows the existing no-ad lifecycle contract; a database failure follows the existing 503 contract rather than pretending inventory is empty.

### Exact and approximate implementations

- Start with CPU IndexFlatIP as the exact reference and initial serving default.
- Implement one CPU IndexHNSWFlat comparison with declared build/search settings. Defer IVF, compression, and GPU support.
- Use a persisted stable index-ID/database-ad-ID association; never treat transient result positions as database IDs. Validate the mapping on build and reload.
- Exact search scans vectors. Its benefit, if measured, may come from cheaper vector similarity and reducing expensive downstream ranking to 500 ads, not avoiding all catalog scans.
- Approximate HNSW search is data-dependent and adds graph storage/build work. Do not promise a universal query complexity or speedup. Record its actual quality, memory, and timing tradeoffs.

### Index lifecycle and fallback

Build immutable replacement snapshots outside request handling. Persist index, ID mapping, and a manifest containing vector/vocabulary version, metric, catalog version, library/build version, count, build settings, and checksums. Validate artifacts before loading or publishing them. A process swaps its active reference only after a complete replacement is ready; in-flight requests retain a valid snapshot.

Catalog changes mark the snapshot stale until rebuilt; stale snapshots do not silently omit new inventory. Missing, corrupt, incompatible, or stale artifacts trigger exact retrieval over the current eligible catalog, visibly marked as degraded/fallback operation. Do not rebuild synchronously on every request or mutate the serving index during searches. Multi-worker loading/publication must keep complete versions and ID mappings paired.

Pin compatible CPU FAISS/NumPy/runtime versions after implementation smoke checks of search, IDs, persistence, and reload. Use the existing Docker target for reproducible validation, and verify native development separately; the research note records current packaging evidence but no successful local installation.

### Ties and measurement

Any eligible members tied at the boundary may fill the candidate set. Order returned candidates consistently by descending similarity and ascending ad ID, without promising globally identical membership among all boundary ties. Ranking applies its own tie rules afterward.

Freeze one catalog/eligibility snapshot and held-out reproducible nonempty query set for quality comparisons. Measure empty-interest fallback separately. Report ordinary ID recall with its tie sensitivity and use tie-aware recall for promotion. For k=min(limit, eligible_count), let G be ads strictly above the exact kth score, T the boundary-tied ads, and R the returned distinct eligible IDs. Tie-aware recall is:

```text
(|R intersect G| + min(|R intersect T|, k - |G|)) / k
```

Declare numeric tolerance before measurement. Recall is undefined for k=0; do not report it as perfect. This formula credits interchangeable boundary members without hiding missed strictly better candidates. Also report returned candidate counts and missed superior candidates.

HNSW may replace the exact default only if the comparison demonstrates lower measured retrieval P95 and at least 95% tie-aware recall on the declared query set. Document aggregation and query-level quality variation rather than hiding poor queries behind one summary. Retrieval latency includes metadata lookup, filtering, expansion, and fallback; also report vector-only latency separately. This gate is a project requirement, not an achieved result.

Report build time, index/artifact size, memory, P50/P95/P99, throughput, fallback rate, and downstream winner/ranking-score differences. High similarity recall does not guarantee retaining the best CTR/bid-ranked ad. Keep hardware, runtime, dataset, queries, ranking strategy, threads, warmup, and concurrency comparable. If the gate fails, keep exact search and publish the result honestly.

### Phase 2 completion and handoff

1. Pass tests for vector construction/normalization, empty interests, invalid vector data, eligibility, ties, candidate limits, ID mapping, and persisted index reload.
2. Pass tests for stale/missing/corrupt/incompatible indexes, eligibility changes, filtering/backfill, and visible fallback behavior.
3. Produce reproducible comparisons of full-ad ranking, exact retrieval plus ranking, and approximate retrieval plus the same ranking. Separate vector search, metadata/filtering, ranking, and total request timings.
4. Record actual results at 100,000 ads before claiming that scale. Smaller tests remain labeled with their actual size. No speedup or downstream improvement is required to complete the phase.
5. Explain exact scan costs, approximate quality/memory tradeoffs, immutable snapshot design, and why reducing downstream ranking work is distinct from ANN acceleration.

The later ranking decision owns scoring formulas, the cache/failure decision extends operational behavior, and the benchmark decision owns final load-test scenarios. No newly exposed decision needs another ticket. Phase 1 must still pass its own completion gate before Phase 2 implementation starts.
