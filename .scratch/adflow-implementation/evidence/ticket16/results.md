# Ticket 16 — Native retrieval component measurements

Measured on 2026-10-08. These are serial offline component experiments on one native Windows host with PostgreSQL colocated. They do not measure HTTP, durable selection/event writes, concurrent capacity, or Phase 8 steady-state workloads. Serving remains Flat; no automatic setting change was made.

The full seed actually contains 1,000 synthetic users, 200 advertisers and 100,000 ads. The small seed contains 100 synthetic users, 20 advertisers and 1,000 ads. Each comparison freezes its own dataset/eligibility and query set; comparisons across dataset sizes are separate experiments.

| Dataset | Eligible ads | Nonempty queries × repetitions | Empty queries × repetitions | Full-ad total P95 ms | Flat retrieval P95 ms | HNSW path incl. fallback P95 ms | HNSW minimum tie-aware recall | Gate eligible |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| small | 1,000 | 20 × 3 | 3 × 3 | 25.933 | 88.558 | 217.470 | 0.986000 | False |
| full | 100,000 | 30 × 3 | 3 × 3 | 3753.757 | 40.715 | 6631.704 | 0.000000 | False |

## Small experiment

Run `0c571188-ebeb-46f8-bdd8-12439799b10d`; dataset `339aa2ad-bd42-582c-9df9-2bd21d1f97d6`; catalog `catalog-v2:339aa2ad-bd42-582c-9df9-2bd21d1f97d6:1020`; source revision `29c0a0b20b8851473b03dda08f24deac3eba6912`.

Config: limit 500, query seed 1601, absolute boundary tolerance 1e-06, 1 FAISS thread, concurrency 1, 5 excluded warmup queries per path. HNSW settings: `{"ef_construction": 200, "ef_search": 128, "m": 32}`. Repetitions reuse one process, catalog and index pair; path order is seeded/interleaved.

| Path | Total P50/P95/P99 ms | Vector P95 ms | Metadata P95 ms | Ranking P95 ms | Personalized fallback rate | Winner changes vs full-ad |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| full_ad | 16.735 / 25.933 / 106.388 | 0.000 | 24.242 | 2.350 | 0.000 | 0 / 60 |
| flat | 36.140 / 95.436 / 108.791 | 1.942 | 87.136 | 1.154 | 0.000 | 0 / 60 |
| hnsw | 119.712 / 228.183 / 241.540 | 3.348 | 42.769 | 1.171 | 0.900 | 0 / 60 |

| Path | Ordinary ID recall mean / min | Tie-aware recall mean / min | Missed superior ads (sum across samples) |
| --- | --- | --- | ---: |
| flat | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 0 |
| hnsw | 0.837600 / 0.560000 | 0.999300 / 0.986000 | 21 |

Personalized HNSW-path modes are separate below. The overall HNSW-path P95 above includes fallback work; it is not nominal ANN-only latency.

| Actual mode | Samples | Full-retrieval P95 ms | Vector-only P95 ms | Mean / minimum tie-aware recall |
| --- | ---: | ---: | ---: | --- |
| exact_fallback | 54 | 223.813 | 3.359 | 1.000000 / 1.000000 |
| hnsw | 6 | 109.201 | 3.348 | 0.993000 / 0.986000 |

Personalized HNSW fallback reasons: `['insufficient_candidates']`. A zero missed-superior count alone does not imply good recall: if the exact top-k lies entirely within one tied maximum group, G is empty and missing that boundary group still produces low/zero tie-aware recall.

| Repetition | Flat full-retrieval P95 ms | HNSW full-retrieval P95 ms |
| --- | ---: | ---: |
| 1 | 32.776 | 130.867 |
| 2 | 100.975 | 135.608 |
| 3 | 43.045 | 224.101 |

| Index | Build + persistence/validation ms | Reload ms | Native file bytes | All artifact bytes | Process RSS after build/load bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| flat | 63.875 | 11.812 | 52,045 | 74,048 | 83222528 |
| hnsw | 164.962 | 13.368 | 323,682 | 345,754 | 84619264 |

Memory before build: `{"peak_rss_bytes": 82612224, "rss_bytes": 82599936, "source": "Windows process working set (cumulative peak)"}`; after measurement: `{"peak_rss_bytes": 95555584, "rss_bytes": 95461376, "source": "Windows process working set (cumulative peak)"}`. These are process-wide observations including frozen data, reference-score maps, harness allocations and indexes, not incremental native index costs. Measurement-loop process CPU: 9.828s, including quality/reporting overhead.

Gate: **gate not met; retain Flat**. Requires strictly lower full-retrieval P95, every query tie-aware recall ≥95%, three repetitions and no personalized fallback. Ordinary ID recall is boundary-tie-sensitive. No serving change was applied.

Separate empty-interest results are retained under `summary.empty_interests` in [small summary](small-summary.json). They carry no cosine recall. Raw per-query candidates, winner bids/scores, all timing/recall distributions and per-repetition results are in [small compressed raw report](small-report.json.gz); the selected inputs are in [small queries](small-queries.json).

Complete local inputs and Flat/HNSW artifacts remain under `artifacts/retrieval-ticket16-small/` (ignored by Git). The committed report includes their manifests/hashes; rerun the recorded preparation commands to regenerate them on another checkout.

## Full experiment

Run `80773bde-0043-4e3b-8228-93b0552b5345`; dataset `caef4b11-279d-57b3-a015-01e0027f1370`; catalog `catalog-v2:caef4b11-279d-57b3-a015-01e0027f1370:100200`; source revision `29c0a0b20b8851473b03dda08f24deac3eba6912`.

Config: limit 500, query seed 1601, absolute boundary tolerance 1e-06, 1 FAISS thread, concurrency 1, 10 excluded warmup queries per path. HNSW settings: `{"ef_construction": 200, "ef_search": 128, "m": 32}`. Repetitions reuse one process, catalog and index pair; path order is seeded/interleaved.

| Path | Total P50/P95/P99 ms | Vector P95 ms | Metadata P95 ms | Ranking P95 ms | Personalized fallback rate | Winner changes vs full-ad |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| full_ad | 2760.846 / 3753.757 / 4084.707 | 0.000 | 3626.487 | 155.413 | 0.000 | 0 / 90 |
| flat | 37.732 / 51.102 / 63.891 | 4.415 | 37.567 | 1.005 | 0.000 | 33 / 90 |
| hnsw | 38.148 / 6639.902 / 7312.315 | 4.955 | 49.753 | 1.277 | 0.100 | 63 / 90 |

| Path | Ordinary ID recall mean / min | Tie-aware recall mean / min | Missed superior ads (sum across samples) |
| --- | --- | --- | ---: |
| flat | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 0 |
| hnsw | 0.514933 / 0.000000 | 0.866667 / 0.000000 | 0 |

Personalized HNSW-path modes are separate below. The overall HNSW-path P95 above includes fallback work; it is not nominal ANN-only latency.

| Actual mode | Samples | Full-retrieval P95 ms | Vector-only P95 ms | Mean / minimum tie-aware recall |
| --- | ---: | ---: | ---: | --- |
| exact_fallback | 9 | 7301.795 | 7.924 | 1.000000 / 1.000000 |
| hnsw | 81 | 37.843 | 3.021 | 0.851852 / 0.000000 |

Personalized HNSW fallback reasons: `['insufficient_candidates']`. A zero missed-superior count alone does not imply good recall: if the exact top-k lies entirely within one tied maximum group, G is empty and missing that boundary group still produces low/zero tie-aware recall.

| Repetition | Flat full-retrieval P95 ms | HNSW full-retrieval P95 ms |
| --- | ---: | ---: |
| 1 | 47.100 | 6693.393 |
| 2 | 38.436 | 6596.025 |
| 3 | 39.249 | 6786.497 |

| Index | Build + persistence/validation ms | Reload ms | Native file bytes | All artifact bytes | Process RSS after build/load bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| flat | 1326.511 | 1002.343 | 5,200,045 | 7,289,161 | 236883968 |
| hnsw | 13106.724 | 1709.978 | 32,420,834 | 34,510,019 | 304627712 |

Memory before build: `{"peak_rss_bytes": 217518080, "rss_bytes": 217505792, "source": "Windows process working set (cumulative peak)"}`; after measurement: `{"peak_rss_bytes": 617623552, "rss_bytes": 614092800, "source": "Windows process working set (cumulative peak)"}`. These are process-wide observations including frozen data, reference-score maps, harness allocations and indexes, not incremental native index costs. Measurement-loop process CPU: 340.125s, including quality/reporting overhead.

Gate: **gate not met; retain Flat**. Requires strictly lower full-retrieval P95, every query tie-aware recall ≥95%, three repetitions and no personalized fallback. Ordinary ID recall is boundary-tie-sensitive. No serving change was applied.

Separate empty-interest results are retained under `summary.empty_interests` in [full summary](full-summary.json). They carry no cosine recall. Raw per-query candidates, winner bids/scores, all timing/recall distributions and per-repetition results are in [full compressed raw report](full-report.json.gz); the selected inputs are in [full queries](full-queries.json).

Complete local inputs and Flat/HNSW artifacts remain under `artifacts/retrieval-ticket16-full/` (ignored by Git). The committed report includes their manifests/hashes; rerun the recorded preparation commands to regenerate them on another checkout.

## Environment and limits

Runtime: `{"byteorder": "little", "faiss_build": "", "faiss_version": "1.15.1", "machine": "AMD64", "numpy_version": "2.2.6", "python_version": "3.10.11", "system": "Windows"}`. Processor: `AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD`; logical CPUs: 16. PostgreSQL: `PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit`. Database and runner share the native host; no Docker memory/CPU limits apply. No other benchmark/test process was intentionally run concurrently during measurement.

Nearest-rank percentiles pool compatible raw samples and are not averages of repetition percentiles. Warmup, seeding, index preparation and exact-reference calculation are outside component timings. Full-ad benchmarking materializes ID/interests/bid metadata so retrieval/metadata and ranking can be timed separately; its O(N) harness memory is not the old streaming selector's memory behavior. Indexed paths include actual current-metadata retrieval. Component totals exclude profile lookup and durable logging and cannot substitute for complete recommendation-request latency.

The limited query sets are component evidence, not universal latency/quality guarantees or independent three-minute HTTP repetitions. Positive percentage speedup, CTR lift and capacity claims are not made. Similarity recall can be high while ranking winners differ; raw winner/bid/overlap results show that distinction. Phase 2's gate remains ticket 17; later HTTP/load comparisons remain separate work.
