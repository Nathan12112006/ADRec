# 11 — Define versioned topic vectors and the retrieval result contract

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 2 — Candidate retrieval
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 10

## Scope

Implement binary user-interest and ad interest/category-union vectors with normalized cosine semantics and versioned vocabulary order. Define CandidateRetriever results with IDs, current metadata, similarity when applicable, modes/versions/counts/timing/fallback reasons; validate configurable limits.

## Dependencies

- [10 — Verify and record the Phase 1 completion gate](10-phase-one-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Tests cover normalization, category deduplication, vocabulary/dimension/finite-value validation and invalid zero-vector ads.
- [x] Empty-interest users have an explicit nonpersonalized path; limits are positive/bounded.
- [x] No bids or artificial dimensions enter vectors; document similarity versus ranking overlap.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Implementation and verification — 2026-10-07

Implemented by Codex using the implement/TDD skills. Nathan confirmed the public topic-vector functions, retrieval input/result contracts and retrieval-settings validation as pure unit-test seams, with the existing HTTP/PostgreSQL suite for regression. Task-start review baseline: `f0c7084a0b844de6782074b7dd88a7c1a8b2b025`. Ticket 10 was done before work began. No ADR directory exists.

Files/behavior:

- `backend/app/core/topics.py` shares the original 13-topic seed order under `topics-v1`; generation imports it without changing generator version, manifest fields or order. Container default seeding retained dataset ID `07415efc-7c8f-5781-92d1-e922d81fa502` (`entities-v1`, seed 42, Python 3.12.15).
- `backend/app/retrieval/vectors.py` provides frozen `TopicVector`, `user_vector` and `ad_vector`. User membership deduplicates interests; ad membership unions interests/category without weighting. Nonempty coordinates are 1/sqrt(distinct memberships), using no bids or artificial dimensions. Empty users return `None` to explicitly bypass search. Unknown topics/categories, zero vectors, wrong vocabulary order/version, dimensions, nonfinite/negative/weighted or unnormalized values are rejected. Absolute coordinate tolerance is 1e-6 for float32 reload; cosine inner products clamp tiny overshoots at one.
- `backend/app/retrieval/contracts.py` defines the replaceable typed `CandidateRetriever.retrieve(user, limit=500)` interface and frozen `RetrievalUser`, `RetrievalCandidate`, `RetrievalResult`. Current detached ad metadata includes stable IDs, decimal bid, payload, eligibility flags and nullable similarity. Result validation enforces distinct capped candidates, required finite cosine scores and similarity/ad-ID order, or null scores and bid/ad-ID order for nonpersonalized fallback. Modes, active index version, vector/vocabulary versions, requested/derived returned counts, finite nonnegative elapsed milliseconds and fallback reasons are explicit and internally consistent. Database error propagation and full monotonic retrieval timing are documented adapter obligations; a result cannot guarantee freshness after retrieval, so selection-time revalidation remains required.
- `backend/app/retrieval/limits.py`, settings, `.env.example` and Compose share candidate bounds (1–500, default 500); future search expansion accepts 1–1,000,000, default 4,000, and must cover the configured candidate limit. These safety bounds are implementation choices, not measured optimization results. The expansion bound does not cap later exact-current-inventory fallback scans.
- Added `backend/tests/unit/test_topic_vectors.py` (23 cases), `test_retrieval_contract.py` (45 cases), and six settings cases. README documents public contracts, cosine versus overlap, fallback/eligibility obligations, configuration, complexity and future-phase boundaries.

TDD: first vector test failed collection because retrieval did not exist, then passed after minimal implementation. Category-union/cosine test failed for the absent ad function, then passed. Successive slices observed actual failures for invalid dimensions/finite/membership values, reordered vocabulary, unknown topics, requested count bounds, duplicate/excess/unordered candidates, current metadata validation, nonpersonalized score/order, inconsistent fallback diagnostics/latencies, environment bounds and expansion below candidate count; each passed after its corresponding implementation. The three-topic self-similarity test caught 1.0000000000000002 versus the mathematical unit cosine, fixed by clamping the rounding overshoot. Additional empty-user, category-only, version, float32, fallback and limited-inventory cases characterize the established contracts. No mocks of internal collaborators or FAISS placeholder implementations were added.

Strict mypy initially flagged Pydantic's computed-field/property decorator limitation. Applied only `# type: ignore[prop-decorator]` on the computed returned-count field, following [Pydantic's documented guidance](https://docs.pydantic.dev/latest/api/fields/#pydantic.fields.computed_field). This derives the reported count from actual candidates rather than trusting a second input count. Initial import-order/format warnings were fixed before final checks.

#### Exact checks

Focused commands from `backend/` were run repeatedly during vertical slices:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_topic_vectors.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/test_retrieval_contract.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/unit/test_topic_vectors.py tests/unit/test_retrieval_contract.py tests/unit/test_config.py tests/unit/test_seed_generation.py -q --tb=short
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m ruff check --fix .
.\.venv\Scripts\python.exe -m ruff format .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Final focused result: **101 passed in 1.16 seconds**. Strict mypy passed **51 source files**, Ruff lint/format passed **51 files**. No dependency, lockfile or schema changes were needed.

From root, Docker checks used only a newly created `adflow-ticket11` project/volume; inventory first confirmed no running containers and no preexisting ticket11 volume. Reviewed outside-sandbox Docker/network execution was required by filesystem/process permissions and succeeded without an unresolved approval rejection:

```powershell
docker compose -p adflow-ticket11 config --quiet
docker compose ls
docker volume ls --filter name=adflow-ticket11
docker ps --format '{{.Names}} {{.Ports}}'
docker compose -p adflow-ticket11 build backend
docker compose -p adflow-ticket11 up -d --wait postgres
docker compose -p adflow-ticket11 run --rm backend python -m alembic upgrade head
docker compose -p adflow-ticket11 run --rm backend python -m app.seeding.cli
docker compose -p adflow-ticket11 exec -T postgres createdb -U adflow adflow_test
docker compose -p adflow-ticket11 up -d --wait
docker build --check backend
docker compose -p adflow-ticket11 exec -T backend python -c "from app.retrieval.vectors import user_vector, ad_vector; from app.core.config import load_settings; user=user_vector(['technology']); assert user is not None; ad=ad_vector(['technology','gaming'], category='gaming'); assert abs(user.similarity(ad)-0.7071067812)<1e-9; assert user_vector([]) is None; settings=load_settings(); assert settings.retrieval_candidate_limit==500 and settings.retrieval_search_limit==4000; print('container vector/config smoke passed')"
docker compose -p adflow-ticket11 run --rm backend python -m alembic check
docker image inspect adflow-backend:phase1 --format '{{.Id}}'
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Compose validation, image build and build check passed (**no warnings**). Linux runtime vector/settings smoke passed; API and PostgreSQL were healthy. Readiness returned `ready`; application Alembic check found no new upgrade operations. Fresh seed produced 100 users, 20 advertisers, 1,000 ads and no recommendation/event history. Image identity: `sha256:7b14db01bc46bf1c453b88a3fc2e1d15095a60610adf0ebc5a0122b6af6797be`. Runtime: Windows CPython 3.10.11/pytest 9.1.1 for tests; existing Linux amd64 CPython 3.12.15/PostgreSQL 18.6, Docker engine 29.4.3/Compose 5.1.3 for containers. Existing locked package/base inputs remain unchanged; other architectures/runtimes are unverified.

Full regression, once at the end, from `backend/`:

```powershell
$env:ADFLOW_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow'
$env:ADFLOW_TEST_DATABASE_URL='postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_test'
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
.\.venv\Scripts\python.exe -m pytest --tb=short
```

**260 passed in 30.52 seconds**: 148 unit and 112 isolated real PostgreSQL integration tests. Existing HTTP/lifecycle/seed/database checks all passed.

Final database check/reconciliation and cleanup from root:

```powershell
docker compose -p adflow-ticket11 run --rm backend python -m alembic -x database=test check
docker compose -p adflow-ticket11 exec -T postgres psql -U adflow -d adflow -Atc "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM advertisers), (SELECT count(*) FROM ads), (SELECT count(*) FROM recommendations), (SELECT count(*) FROM events)"
docker compose -p adflow-ticket11 ps
docker compose -p adflow-ticket11 down
git diff --check
```

#### Limits and handoff

Vector construction/validation takes O(D + I) time/space for D=13 dimensions and I input interests; inner product takes O(D). Result validation takes O(K log K) time/O(K) space for K<=500 plus candidate topic validation. These are algorithm explanations, not performance results. Serving still uses the Phase 1 overlap selector, which neither normalizes nor adds category membership. This ticket supplies the empty-interest path and fallback result contract, while ticket 13 implements current-inventory bid fallback/filtering/backfill. Ticket 12 owns FAISS/NumPy installation and immutable index artifacts; no search index, fallback adapter, model, new serving path or performance claim is implemented here. Phase 2 is not complete; ticket 12 is next, and ticket 17 remains its technical gate. No human learning checkpoint is certified by this work.

### Review and completion

Committed implementation as `aa435f0` on the existing `main` branch. Final test-database
Alembic check found no new upgrade operations. Post-suite demo counts stayed
`100|20|1000|0|0`, confirming isolated test execution preserved the seeded application
database. Both containers were healthy before successful `down`; containers/network
were removed, while `adflow-ticket11_postgres_data` and its history were retained.

The code-review skill used independent read-only Standards and Spec sub-agents over
`git diff f0c7084a0b844de6782074b7dd88a7c1a8b2b025...HEAD`, with task-start HEAD as the
fixed baseline. Reviewers inspected the recorded results without rerunning checks.

#### Standards

No documented-standard breaches or actionable baseline smells found. Domain language,
execution evidence, shared vocabulary, cohesive validation and local/Compose
configuration follow repository rules. The required retrieval protocol stays limited
to its documented interface. **0 findings**.

#### Spec

No missing/partial requirements, scope creep or wrong implementation found. Binary
membership, category union, normalization/validation, empty-user path, metadata,
ordering, diagnostics and bounded limits satisfy ticket 11. FAISS and concrete
current-inventory fallback remain in tickets 12/13; Phase 1 serving remains unchanged.
**0 findings**.

Review total: Standards 0, Spec 0; neither axis has an outstanding issue. No fixes or
additional test runs were needed after review. The follow-up commit records review
and cleanup evidence only. `git diff --check` passed; the working tree was clean after
committing. Ticket 11 is done; ticket 12 remains open and is now unblocked.
