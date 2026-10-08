# 14 — Add the HNSW candidate-retrieval comparison

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 10, 12, 13

## Scope

Implement one CPU IndexHNSWFlat option using the same vectors, ID mapping, artifact validation and eligibility pipeline as Flat. Expose documented build/search settings for controlled comparison; retain exact as the serving default pending measured promotion.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)
- [12 — Build and reload exact FAISS index snapshots](12-flat-index-artifacts.md)
- [13 — Implement current eligibility filtering and exact fallback](13-eligibility-backfill.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Exact/approximate options share candidate/result interfaces and bounds.
- [x] Tests tolerate boundary-tied membership but preserve eligible/distinct results and ordering.
- [x] Record graph/build/search settings and costs; defer IVF/compression/GPU.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification

Implemented CPU `IndexHNSWFlat` as an opt-in snapshot family behind the same build/load/search, active reload, and current-eligibility retriever interfaces as Flat. Flat remains the default. Both families use the same normalized 13-topic float32 vectors, sorted external-ID mapping, checksums, reconstructed-vector validation, metadata refresh, candidate bounds, exact fallback, and failure diagnostics. Schema 2 records the index family and settings; original schema-1 Flat artifacts remain loadable with their original identity. HNSW loading checks native storage, metric, dimensions/count, graph degree, construction/search depths, and fixed search-policy flags against the manifest.

Build settings are `m=32` (project bounds 2–128), `ef_construction=200` (at least m, at most 1,000,000), and persisted `ef_search=128` (1–1,000,000). Per-query overrides use independent native `SearchParametersHNSW` objects and do not mutate the loaded graph. Search uses inner product, bounded queues, and relative-distance checks. Successful HNSW results report actual search depth; exact fallback reports its existing explicit reason. CLI and README document both families, settings, memory/preparation tradeoffs, and deferred comparison gates. A narrow typed bridge covers native members omitted from the pinned FAISS stubs; no dependency pins changed.

The user approved public snapshot build/load/search/reload, offline CLI, and `CandidateRetriever.retrieve` test boundaries with real FAISS and isolated PostgreSQL, including ties, settings, eligibility, and fallback. TDD exposed the initially missing HNSW build interface and proceeded through focused artifact, CLI, and retrieval checks. New coverage includes persisted settings and known cosines, concurrent overrides without mutation, malformed settings/artifacts retaining the previous reference, legacy Flat loading, both-family current eligibility/revision changes/missing IDs, and shared bounded/distinct/ordered candidate contracts. The schema-rejection fixture now uses unsupported schema 999 because schema 2 is implemented.

A 503-ad all-tied HNSW fixture could not fill a 500-candidate request even at search depth 1024. The correct result is the existing marked `insufficient_candidates` exact fallback, which scans all 503 current eligible ads. The test accepts interchangeable tied membership and verifies the fallback diagnostic instead of requiring nominal approximate success. HNSW coverage is not guaranteed by a large search depth.

Final verification on Windows CPython 3.10.11, FAISS 1.15.1, NumPy 2.2.6:

- Full suite: **390 passed in 62.73 seconds** (220 unit, 170 isolated PostgreSQL integration), including 45 added cases.
- Focused HNSW snapshots: 23 passed; snapshots plus CLI: 31 passed; the final shared tied-boundary cases: 2 passed. Earlier focused current-retrieval run: 45 passed before those two final cases were added.
- Strict mypy, Ruff lint, and Ruff format: all 61 files passed; `git diff --check` passed.
- Application and test database `alembic check`: no new upgrade operations detected.
- Compose configuration, backend image build, and `docker build --check backend` passed without warnings. Readiness returned `{"status":"ready"}`.

### Reproducible runtime smoke evidence

Used isolated Compose project `adflow-ticket14`, PostgreSQL 18.6, Linux x86_64 CPython 3.12.15, FAISS 1.15.1 (`OPTIMIZE DD AVX2`), NumPy 2.2.6, and one FAISS thread. Image identity: `sha256:36a66b265ec1e5a4ab1505bd253f60d740e1dfb3575b1f43fa2dff6804286a0e`. Migrated and seeded the default 100 users / 20 advertisers / 1,000 ads. Dataset `07415efc-7c8f-5781-92d1-e922d81fa502`, catalog `catalog-v2:07415efc-7c8f-5781-92d1-e922d81fa502:1020`. Catalog export took 78.933 ms. Local smoke script is retained, ignored, at `.uv-cache/ticket14-smoke.py`; Docker artifact root is `/artifacts/ticket14-smoke`.

One-shot costs (milliseconds), including full artifact validation during preparation:

| Runtime / family | Prepare | Reload | Full retrieval | Vector search | Metadata | Index bytes | ID bytes | Manifest bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Linux Flat | 38.065 | 8.624 | 11.426 | 2.971 | 8.455 | 52,045 | 20,874 | 1,105 |
| Linux HNSW 32/200/128 | 107.301 | 9.410 | 8.258 | 1.302 | 6.955 | 323,682 | 20,874 | 1,170 |
| Windows Flat | 45.995 | 40.678 | 15.114 | 0.189 | 14.925 | 52,045 | 20,874 | 1,130 |
| Windows HNSW 32/200/128 | 136.540 | 10.294 | 13.157 | 0.383 | 12.774 | 323,682 | 20,874 | 1,199 |

Linux Flat snapshot `fc6a4bf9-162a-48fe-a680-34610aa46e6b`; HNSW snapshot `9dbb070b-a26b-4452-bf4f-351873008038`. Their index SHA-256 values are respectively `5df9750aab97a4d3d75fa44b8de2e7ec215f9644cd613e57bd6ad6347da0a92b` and `02b9a9d3462946aefd0e6ecfd9f7f072ad4441470e1b8f67d75cb85ab5c9493b`. Shared ID-mapping SHA-256: `93c93fc5d5d70ce15b4f36dbc813a073d792c38ee0e4567b2f0bf476945d72b9`.

Both runtimes verified known fixture cosines 1, approximately 0.70710678, and 0; three current eligible results for technology/gaming; HNSW per-query depth 256 without changing persisted 128; rollback-only deactivation causing stale-catalog fallback scanning 999 ads; restoration to nominal indexed retrieval; and null cosine for empty interests. Flat and HNSW returned different equally scored third members (all scores approximately 1), as allowed. Windows snapshots were retained under `.uv-cache/ticket14-native`; its HNSW graph checksum differs from Linux, and runtime validation requires rebuilding rather than cross-runtime binary reuse.

Also exercised actual Docker CLI build with `--index hnsw --hnsw-m 16 --ef-construction 80 --ef-search 64 --threads 1`, then load/query with `--ef-search 32`: snapshot `be9bba8e-4eac-4b67-bc4a-076545bab944`, 1,000 ads, query reports 32 while manifest retains 64. Native installed `adflow-index` load/query with depth 64 likewise retained manifest depth 128. Post-suite application database counts remained `100|20|1000|0|0|1020` (users, advertisers, ads, recommendations, events, revision). Containers were stopped with `docker compose -p adflow-ticket14 down`; data and artifact volumes were retained.

These are correctness smoke timings, not warmed benchmarks, P95, recall, resident-memory measurements, or speed comparisons; build order and runtime caches can affect them. Artifact bytes record observed storage costs. Full ranking/Flat/HNSW controlled comparison, canonical tie-aware recall, 100,000-ad evidence and promotion remain ticket 16; serving integration remains ticket 15. No HNSW promotion, IVF/compression/GPU implementation, phase completion, or human checkpoint completion is claimed.
