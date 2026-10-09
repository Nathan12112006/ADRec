# AdFlow

A personalized advertising recommendation demo using synthetic data. The backend provides
reproducible entity seeding, durable recommendation replay, client-confirmed impressions,
attributed clicks and simulated revenue through a synchronous PostgreSQL-backed API.
Health checks, structured request logging and a backend/PostgreSQL Docker demo are available.

Phase 1's technical gate passed on 2026-10-07: fresh migrations/default seeding,
Docker and local startup, lifecycle replay/count reconciliation, database-outage health
behavior, and 186 unit/PostgreSQL tests. See [ticket 10's commands and evidence](.scratch/adflow-implementation/issues/10-phase-one-gate.md).
Phase 2 topic vectors, CPU Flat/HNSW snapshots and current-inventory candidate
retrieval with marked fallback and bounded recommendation serving are available. The
[Phase 2 technical gate](.scratch/adflow-implementation/issues/17-retrieval-gate.md)
passed on 2026-10-08; Flat remains the serving default after HNSW failed promotion.
CTR modeling,
experiments, Redis, dashboards and HTTP load tests remain planned work.
Independent historical exposure artifacts are available for offline model development;
generation is explicit and never adds live recommendations or events.
The separate [lifecycle learning checkpoint](.scratch/adflow-implementation/issues/57-learning-lifecycle.md)
remains open; passing software checks does not certify human understanding.

## Docker demo

Start Docker Desktop with Linux containers and Docker Compose. From the repository root,
prepare a fresh demo explicitly, then start it normally:

```powershell
docker compose config --quiet
docker compose build backend
docker compose up -d --wait postgres
docker compose run --rm backend python -m alembic upgrade head
docker compose run --rm backend python -m app.seeding.cli
docker compose up -d --wait
docker compose ps
```

Open [Swagger UI](http://127.0.0.1:8000/docs),
[liveness](http://127.0.0.1:8000/health/live) or
[readiness](http://127.0.0.1:8000/health/ready), then follow the HTTP walkthrough below.
Preparation creates only the small default entity dataset. Migration and seeding are
separate from ordinary `docker compose up -d --wait`; neither runs on API startup.
No historical labels, model training, index builds or later services are included.
Readiness tests database reachability; it does not certify migration/seed preparation.

The backend image uses digest-pinned Python 3.12.15 and uv 0.12.23, installs runtime wheels
from `uv.lock` with `--locked --no-dev --no-install-project`, and runs source from `/app`.
This avoids resolving a separate build backend. The image contains no uv, test tools,
local virtual environment or dotenv secrets. Run the seed as `python -m app.seeding.cli`
inside the image; local installation also provides the `adflow-seed` entry point.
The API runs as UID/GID 10001 and has a readiness health check. PostgreSQL is health-checked
before dependent containers start. Mechanisms follow official
[uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/) and
[Compose startup ordering](https://docs.docker.com/compose/how-tos/startup-order/).

Compose publishes only loopback ports 8000 (API) and 5432 (PostgreSQL), with disposable
`adflow`/`adflow` credentials and application database `adflow`. Container database URLs use
the `postgres` service hostname. The local `.env.example` URLs use `127.0.0.1`; Compose
overrides these two URLs and reads log/pool/timeout values from the host environment or
root `.env`. Create `.env` from the example once for the local backend; Compose defaults
need no dotenv file. Change port mappings and matching host URLs together if occupied.
These settings are for the local demo, with no public hosting setup.
Use explicit IPv4 host URLs to match the published bind address: on this Windows host,
`localhost` first tried IPv6 and added a measured five-second fallback per new connection.

The project-scoped named volume `postgres_data` retains entities and lifecycle history.
PostgreSQL 18 mounts it at `/var/lib/postgresql` with versioned PGDATA, following the
[official PostgreSQL image](https://hub.docker.com/_/postgres). Ordinary stop/start and
`docker compose down` retain that volume. Repeated identical seeds are no-ops; different
manifests refuse replacement. Manifests include the Python version, so switching local/
container runtimes can change dataset identity: skip reseeding a prepared database or
use a new isolated project/database. There is no startup replacement or cleanup.

```powershell
docker compose logs --tail 50 backend
docker compose down
# Resume the same prepared database later:
docker compose up -d --wait
```

For a separate fresh demonstration, use a new Compose project name consistently with
every command (`docker compose -p adflow-new ...`), after stopping any project using the
same host ports. This creates a separate volume; it does not replace earlier history.
Do not add `--volumes` to normal shutdown commands. Image updates are explicit changes
to pinned image identities followed by rebuild and verification.

## Isolated tests with Compose PostgreSQL

Start PostgreSQL as above. Create the test database once, explicitly; it is never created
by API startup. From the repository root:

```powershell
docker compose exec -T postgres createdb -U adflow adflow_test
docker compose run --rm backend python -m alembic -x database=test upgrade head
```

If `createdb` reports that the database already exists, keep it and run migrations; do
not reset it. Install the local development dependencies below and use `.env.example`
host URLs. Run from `backend/` in PowerShell:

```powershell
$env:ADFLOW_RUN_POSTGRES_TESTS = '1'
uv run --locked pytest
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Integration fixtures append unique test datasets and run serially against `adflow_test`.
They never reset the application database. The runtime image intentionally excludes
development dependencies; run the full suite locally against containerized PostgreSQL.

## Install and run locally

The local development environment uses Windows CPython 3.10.11 and uv 0.12.23; the Docker
runtime uses Linux CPython 3.12.15. The package declares Python 3.10–3.14; remaining
runtimes/platforms have not been exercised. Run from the repository root
in PowerShell (the `uv` commands also work in other shells):

```powershell
python -m pip install uv==0.12.23
Copy-Item .env.example .env
Set-Location backend
uv sync --locked
uv run --locked python -c "from app.main import create_app; create_app(); print('configuration valid')"
# Explicit preparation for a fresh local database; skip seed if already prepared in Docker:
uv run --locked alembic upgrade head
uv run --locked adflow-seed
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open [Swagger UI](http://127.0.0.1:8000/docs) or
[OpenAPI](http://127.0.0.1:8000/openapi.json). Importing
`app.main` alone needs no configuration; calling `create_app()` validates configuration.
Startup creates a lazy connection pool, without connecting or creating tables. Shutdown
disposes the pool. Stop the server with Ctrl+C. Set up the database explicitly below before
using the recommendation and event endpoints.
If Docker already prepared the database, skip the seed command and reuse its entities.
Stop the Compose backend (`docker compose stop backend` from the root) before starting
local Uvicorn on port 8000; leave Compose PostgreSQL running. Restore the container API
later with `docker compose up -d --wait backend`.

`uv.lock` pins runtime, development, and build dependencies. Hatchling is included in the
development group so `uv build --no-build-isolation` uses the locked environment instead
of independently resolving a build backend. `--locked` rejects stale project metadata.
Dependency updates must deliberately regenerate
the lock with `uv lock`, then repeat the checks below. `.venv` and local secrets are ignored.

## Configuration

The loader reads the root `.env` regardless of the working directory; environment variables
override it. `load_settings(env_file=None)` disables dotenv loading for isolated tests.
Names have the `ADFLOW_` prefix. Unknown dotenv keys fail validation to catch mistakes.

| Variable | Default | Contract |
| --- | --- | --- |
| `DATABASE_URL` | required | Application PostgreSQL URL |
| `TEST_DATABASE_URL` | required | Isolated test PostgreSQL URL with a distinct database name |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, or CRITICAL |
| `DB_CONNECT_TIMEOUT_SECONDS` | 5 | Integer, 1–30 seconds |
| `DB_POOL_TIMEOUT_SECONDS` | 5 | Integer, 1–30 seconds |
| `DB_STATEMENT_TIMEOUT_SECONDS` | 5 | Integer, 1–30 seconds per SQL statement |
| `DB_LOCK_TIMEOUT_SECONDS` | 3 | Integer, 1–30 seconds waiting for a PostgreSQL lock |
| `DB_POOL_SIZE` | 5 | Integer, 1–20 connections |
| `DB_MAX_OVERFLOW` | 5 | Integer, 0–20 additional connections |
| `RETRIEVAL_CANDIDATE_LIMIT` | 500 | Integer, 1–500 candidates; not yet used by serving |
| `RETRIEVAL_SEARCH_LIMIT` | 4000 | Integer, 1–1,000,000; at least candidate limit; future search expansion bound |

Database URLs use `postgresql+psycopg://user:password@host:port/database`. URL-encode
special characters in credentials. Query options are rejected so alternate hosts/database
names and timeout overrides cannot bypass configuration checks. Database names must differ
even across hosts, credentials, and encoded names. This is a configuration guard, not proof
of database permissions or runtime connectivity. The database adapter applies these limits,
sets the connection timezone to UTC, and disconnects sessions left idle in a transaction for
30 seconds. Statement timeouts bound server execution, not an end-to-end HTTP deadline.
`ADFLOW_LOG_LEVEL` controls application request logging. Uvicorn's `--log-level` option
controls server logs separately.

Both URLs are secret fields, hidden in normal settings representations. The environment
loader raises `ConfigurationError` containing only field locations and error codes, never
raw input values. Do not log explicit secret extraction or raw validation `.errors()` data.
The credentials in `.env.example` are disposable local demo values.

## Checks

Run from `backend/` after `uv sync --locked`:

```powershell
uv run --locked pytest tests/unit/test_config.py
uv run --locked pytest tests/unit/test_app.py
uv run --locked pytest tests/integration
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv build --no-build-isolation
```

The unit tests require no running PostgreSQL server; health failure checks attempt a
connection to an unavailable local port. TestClient exercises
the real ASGI app and synchronous request dependencies in process. On this Codex Windows
host, TestClient's event loop requires running outside the execution sandbox; normal local
execution works. Integration tests are skipped unless `ADFLOW_RUN_POSTGRES_TESTS=1`.
They run migrations on `TEST_DATABASE_URL`, add uniquely identified fixtures, and test real
constraints and timeouts. They do not drop or reset a database. Negative tests attempt
history mutations/truncation that the database must reject, so use a dedicated disposable
test database. With a configured root `.env`, run in PowerShell:

```powershell
$env:ADFLOW_RUN_POSTGRES_TESTS = "1"
uv run --locked pytest
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
```

This includes all unit and PostgreSQL tests. PostgreSQL 18.6 is used by the Compose demo
and the earlier native Windows checks. Native checks used official
[EDB portable binaries](https://www.enterprisedb.com/download-postgresql-binaries).

## PostgreSQL setup and migrations

Use a PostgreSQL server you control with separate development and test databases. The
example `.env` targets port 5432. To use only the Compose database with local Uvicorn,
run from the repository root:

```powershell
docker compose up -d --wait postgres
docker compose exec -T postgres createdb -U adflow adflow_test
```

`--wait` checks PostgreSQL health before continuing. With a native server,
create both databases with `createdb -h localhost -U adflow adflow` and
`createdb -h localhost -U adflow adflow_test`, using the configured account and password.
Creating databases is explicit; the app and migrations never create a database.

Run from `backend/` after installation and configuration:

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
uv run --locked alembic -x database=test upgrade head
uv run --locked alembic -x database=test check
uv run --locked alembic upgrade head --sql
```

The default target is the application URL. `-x database=test` explicitly selects the isolated
test URL; unknown target names fail. `check` detects ORM/schema drift; `--sql` generates SQL
without connecting. Repeated upgrades at head preserve all data. Revision `0001` creates
the schema, revision `0002` protects durable history, and revision `0003` tracks catalog
freshness separately from immutable provenance. Downgrades are intentionally
unsupported: use a newly named disposable database to repeat a fresh setup.

## Synthetic entity seeds

After `uv sync --locked` and explicit migrations, run from `backend/`:

```powershell
uv run --locked adflow-seed
uv run --locked adflow-seed --seed 123 --users 100 --advertisers 20 --ads 1000
uv run --locked adflow-seed --users 10000 --advertisers 100 --ads 100000
uv run --locked adflow-seed --database test --seed 123 --users 5 --advertisers 2 --ads 10
```

Each command is a separate choice of dataset. The default is seed 42 with 100 users,
20 advertisers and 1,000 ads. No request outcomes, recommendations, impressions or clicks
are generated. FAISS, ML, Redis and experiments are not required. `python -m app.seeding.cli`
is an equivalent entry point; `--help` works without database configuration.

Counts must be nonnegative; ads require at least one advertiser. `--batch-size` accepts
1–10,000 (default 1,000) and changes write buffering, not generated data. The CLI prints
JSON containing dataset identity, requested counts, status and the complete manifest.
Exit codes are 0 for success/no-op, 2 for invalid settings or a dataset conflict, and 3
for database failure (all writes rolled back). It never runs migrations implicitly.

Repeating identical inputs reports `already_exists` and changes nothing, even if inventory
has subsequently been edited. Counts in that response describe the original seed, not a
fresh audit or repair. Different inputs refuse to write when a dataset already exists.
Use a fresh database for replacement, or deliberately add inventory with:

```powershell
uv run --locked adflow-seed --seed 123 --users 100 --advertisers 20 --ads 1000 --append
```

Append preserves existing entities and lifecycle history; it also expands the inventory
available to subsequent serving. No replacement/delete/reset flag exists. A transaction-level
advisory lock serializes cooperating seeders with the configured lock timeout. One transaction
contains provenance and every batch, so any failure rolls back the entire seed.

The `entities-v1` generator uses the brief's 13 topics as categories, with documented related
interests (for example gaming/technology and fitness/sports). Users sample 1–5 unique interests
uniformly, then 1–3 category preferences from those interests. Age group, country and device
use uniform choices from the lists stored in the manifest. Advertiser topics, ad categories
and advertiser associations are uniform. All generated advertisers and ads are active.
Bids are uniform integer cents from $0.25–$5.00, converted directly to `Decimal`. Empty-interest
users, zero bids and inactive inventory remain separate edge fixtures. These distributions
are designed synthetic assumptions, not population estimates or observed click behavior.

Separate SHA-256-derived random streams generate users, advertisers and ads. Changing profile
counts does not consume the ad stream. The manifest records the seed, counts, generator/Python
versions, vocabulary, relationships and distributions; historical counts are zero and time
ranges/splits are null. Generation is reproducible within the recorded Python runtime. Dataset
creation time records loading time and is not a simulated entity timestamp.

A UUID derived from the complete manifest identifies each dataset. Positive 63-bit entity IDs
derive from dataset/type/position, so references repeat independently of database sequence state
and batch size. Changing configuration changes dataset and reference IDs. A rare hash-ID collision
causes a constraint failure and full rollback, never an overwrite. Bounded batch insertion uses
O(batch size) working memory and O(users + advertisers + ads) generation work, plus database index
maintenance. Large seeds keep one transaction open and may need smaller batches on slow hosts;
this is an explicit development operation, not a request path or automatic startup task.

See [SQLAlchemy bulk inserts](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-bulk-insert-statements),
[PostgreSQL advisory locks](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS),
and [Python random reproducibility](https://docs.python.org/3.10/library/random.html#notes-on-reproducibility)
for the underlying APIs. Seed tests run with the normal unit/PostgreSQL commands above.

## Baseline selection

`app.ranking.select_baseline(user_interests, candidates)` is a pure selector over an
iterable of immutable `BaselineCandidate` values. It returns the winning candidate or
`None` for a no-ad outcome. Only active ads from active advertisers qualify. Distinct
shared interests rank first, then the higher decimal bid, then ascending ad ID. Duplicated
interests count once; empty interests/no overlaps reduce selection to bid and ID.
Zero bids remain eligible. Eligible negative or nonfinite bids raise `ValueError`.
Ad category is not added to target interests for this baseline. No model is invoked
and no predicted CTR is produced.

`app.db.selection.select_baseline_ad(session, user_interests)` reads current eligible
inventory through a PostgreSQL join and supplies it to that same selector. It streams
only ID, interests and bid in batches of up to 1,000 rows. It returns a detached immutable
candidate and closes the result cursor; the caller owns the session/transaction. This
read does not lock inventory or save recommendations. Ticket 05 owns persistence and
eligibility/bid revalidation before a recommendation is committed.

With N eligible ads, U user interests and up to A interests per ad, expected hash-set
selection work is O(U + N*A), with O(U + A) selector working space. The database adapter
adds O(B*A) client buffering for batch size B=1,000, plus driver overhead. The database
still scans/joins inventory and transmits every eligible candidate; this is not a
serving performance claim. Later candidate retrieval bounds the set passed to selection.
SQLAlchemy documents the streaming behavior in
[Fetching large result sets with yield_per](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per).

Focused checks from `backend/`:

```powershell
uv run --locked pytest tests/unit/test_baseline.py
# With the isolated PostgreSQL test URL configured:
$env:ADFLOW_RUN_POSTGRES_TESTS = "1"
uv run --locked pytest tests/integration/test_baseline_selection.py
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
```

Database selector fixtures temporarily hide existing ads and add edge inventory inside
rollback-only test transactions. They never commit those edits or clear history. Use
the dedicated test database and run this suite serially, as with the other integration checks.

## Topic vectors and candidate-retrieval contract

Topic vectors and validated retrieval inputs/results feed offline FAISS snapshots and
current-inventory filtering/fallback. Recommendation serving ranks only the retrieved
candidate set with the Phase 1 overlap selector; no speedup is claimed here.

`app.core.topics.TOPICS` preserves the seed generator's 13-topic order, versioned as
`topics-v1`. `app.retrieval.vectors.user_vector(interests)` returns a frozen `TopicVector`
or `None` for an empty-interest user. `ad_vector(interests, category=...)` includes the
union of interests and category exactly once. Nonempty binary membership is divided by
the square root of its distinct topic count (`binary-cosine-v1`); its inner product is
cosine similarity. For example, technology alone versus technology/gaming scores
approximately 0.70710678. Bids never enter these vectors, and there are no padded dimensions.

Vectors validate exact vocabulary order/versions, 13 dimensions, finite nonnegative
values and normalized binary membership. Unknown topics/categories and zero-vector ads
are errors. Loading permits absolute per-coordinate error up to 1e-6 for float32 round
trips; the pure similarity helper clamps tiny rounding overshoots at one. A vocabulary
or vector-rule change requires a new version and compatible rebuilt artifacts. Seeding
imports the same ordered topics; its manifest format and dataset identities are unchanged.

`CandidateRetriever.retrieve(user, limit=500)` is a typed interface implemented by
`CurrentCandidateRetriever`. `RetrievalUser` supplies user ID, dataset ID and interests.
`RetrievalCandidate` supplies stable ad/advertiser/dataset IDs, current ad payload,
decimal bid, eligibility flags and nullable similarity. Constructing a candidate rejects
inactive flags, invalid IDs/money/topics and nonfinite/out-of-range similarity. Callers
must batch-load current metadata and recheck selection-time eligibility; a frozen
result cannot guarantee that catalog data stays current after retrieval.

`RetrievalResult` reports mode, index version when applicable, vector/vocabulary versions,
requested count, derived returned count, full retrieval `elapsed_ms`, and fallback reason.
It rejects duplicate/excess candidates and inconsistent order/diagnostics:

| Mode | Ordering and scores | Index/fallback diagnostics |
| --- | --- | --- |
| `exact` / `hnsw` | Descending cosine similarity, ascending ad ID for ties | Required index version; no fallback reason |
| `exact_fallback` | Same cosine order | No active index; `missing_index`, `corrupt_index`, `incompatible_index`, `stale_index` or `insufficient_candidates` |
| `nonpersonalized` | Descending bid, ascending ad ID; similarity is null | No index; `empty_interests` |

Empty-interest users bypass cosine search and use current-inventory bid/ID ordering. Limited inventory
may yield fewer candidates or zero. Database failures must propagate to the existing 503
handling rather than masquerade as empty inventory. Retrieval timing must include metadata,
filtering, expansion and fallback, and use a monotonic clock in concrete implementations.
Ranking chooses the winner afterward. Phase 1 overlap counts shared interests without
normalization or category union; cosine retrieval and ranking overlap have different meanings.
Boundary ties may have interchangeable membership; returned members still follow consistent order.

`ADFLOW_RETRIEVAL_CANDIDATE_LIMIT` defaults to 500 and accepts 1–500;
`ADFLOW_RETRIEVAL_SEARCH_LIMIT` defaults to 4,000 and accepts 1–1,000,000, at least the
candidate limit. The latter bounds filtered-search expansion before exact fallback;
it does not cap eligible-inventory fallback scans or represent a measured tuning result.
Both settings load locally and pass through Compose. They do not alter Phase 1 serving yet.

Construction/validation costs O(D + I) time and O(D + I) working space for D vocabulary
dimensions and I input interests. Similarity takes O(D) time. Result validation uses
O(K log K) time and O(K) space for K candidates (at most 500), plus candidate topic
validation. These are algorithm costs, not measured latency claims.

Focused checks from `backend/`:

```powershell
uv run --locked pytest tests/unit/test_topic_vectors.py tests/unit/test_retrieval_contract.py tests/unit/test_config.py tests/unit/test_seed_generation.py
uv run --locked mypy
```

Returned count is a Pydantic computed field so it cannot disagree with candidates.
Its narrowly scoped mypy decorator suppression follows the
[Pydantic computed-field guidance](https://docs.pydantic.dev/latest/api/fields/#pydantic.fields.computed_field).

## Offline CPU FAISS snapshots

CPU FAISS is pinned to `faiss-cpu==1.15.1`. NumPy is pinned to `2.2.6` for Python
3.10–3.13 and `2.3.5` for Python 3.14, whose wheels need the newer pin. Native Windows
CPython 3.10.11 and Linux container CPython 3.12.15 passed real build/search/persistence/
reload checks with NumPy 2.2.6. Python 3.14 and other architectures remain unverified.
Package-wheel availability comes from [FAISS](https://pypi.org/project/faiss-cpu/1.15.1/)
and [NumPy](https://pypi.org/project/numpy/2.3.5/); successful installation alone is not
runtime compatibility evidence.

After explicit migrations and entity seeding, prepare a new immutable version from one
dataset. From the root with Compose running:

```powershell
$datasetId = (docker compose exec -T postgres psql -U adflow -d adflow -Atc 'SELECT id FROM datasets ORDER BY created_at LIMIT 1').Trim()
docker compose run --rm backend python -m app.retrieval.cli build --dataset-id $datasetId --output /artifacts/exact-v1
docker compose run --rm backend python -m app.retrieval.cli load /artifacts/exact-v1 --dataset-id $datasetId --interests technology gaming --limit 3
```

Choose the intended dataset explicitly if multiple datasets exist. `build --database test`
selects the isolated test URL; application is the default. Build never migrates, seeds,
replaces catalog data or overwrites an existing version directory. CLI JSON reports the
complete manifest, and `load` optionally reports vector-search hits. `--threads` defaults
to one (accepts 1–64) and configures this offline command's native threads. Search returns
database IDs, not FAISS row positions. It orders returned members by descending cosine
then ascending ad ID; membership among equal boundary scores may differ. Low-level search
accepts 1–1,000,000 hits for bounded expansion; downstream candidate results
remain capped at 500. Empty-user nonpersonalized retrieval is separate from the
cosine-query option in this CLI.

Compose's project-scoped `index_artifacts` volume mounts at `/artifacts`, owned by runtime
UID/GID 10001. Normal `down` retains this volume alongside PostgreSQL data. Build/reload
remain explicit: ordinary API startup creates no index. Store each complete version in
its own new directory; retain old versions for in-flight work and reproducibility.

For local operation, use the existing host database settings and run from `backend/`:

```powershell
uv sync --locked
uv run --locked adflow-index build --dataset-id $datasetId --output ../artifacts/exact-local-v1
uv run --locked adflow-index load ../artifacts/exact-local-v1 --interests technology gaming --limit 3
```

Root `artifacts/` is ignored by Git; preserve needed artifacts separately. The container
runs source directly, so its command is `python -m app.retrieval.cli`; local editable
installation also supplies `adflow-index`.

`read_catalog(session, dataset_id)` exports active ads with active advertisers while holding
a shared lock on that dataset's catalog revision row until the caller ends the transaction.
Catalog writers cannot commit during this offline export, pairing the recorded revision with
one coherent inventory. The CLI closes the export transaction before building FAISS artifacts.
Invalid eligible topics abort the build. Migration `0003` introduces separate mutable
`catalog_revisions`; dataset provenance remains immutable. Its `catalog-v2:<dataset>:<revision>`
token replaces ticket 12's content fingerprint. Rebuild older `catalog-v1` snapshots after
migration; retrieval marks them stale. Existing datasets receive an initial revision row.

Each version contains `index.faiss`, `ids.json` (sorted positive int64 database IDs paired
with sequential FAISS rows), and `manifest.json`. The manifest records schema/builder and
snapshot versions, dataset/catalog identity, vector/vocabulary versions/order, dimension,
metric/dtype, count, native build thread count, runtime/library/build identity, and SHA-256
checksums. Build stages a sibling directory, validates a complete reload, then renames it
into place. Failed writes never publish a partial output version.

New snapshots use schema 2 / builder `cpu-snapshot-v2` and declare `index_type` plus
`hnsw` settings (null for Flat). The loader also accepts original schema 1 /
`flat-snapshot-v1` Flat artifacts with their original version identity. HNSW artifacts
require every declared setting and native graph/storage agreement before activation.

`load_snapshot(path)` reads each payload once, validates checksums before native decoding,
checks complete schema/runtime/mapping/index agreement, and revalidates every stored vector
in batches. It conservatively requires exact FAISS/NumPy/Python version, OS/architecture,
byte order and native compile-option identity. Rebuild in the target runtime rather than
copying Windows artifacts into Linux or relying on untested compatibility. Optional
`expected_dataset_id` and `expected_catalog_version` reject mismatched/stale artifacts;
CLI equivalents are `--dataset-id` and `--expected-catalog-version`. Without a current
expected catalog version, standalone loading validates integrity, not catalog freshness.
Checksums protect accidental corruption, not authenticity: use locally generated trusted
artifacts. FAISS documents that its native reader does not validate arbitrary input in
[index I/O guidance](https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning).

`ActiveSnapshot.reload(path, ...)` performs all file/native work before taking a brief lock
to replace its reference. `snapshot = active.acquire()` obtains a complete version/mapping
pair; already acquired snapshots remain usable after reload. Public snapshots expose search
and a frozen manifest, without live add/remove methods. Every worker must explicitly load
the same complete version path; there is no automatic cross-process rollout. CLI `load`
validates/loads only its own process and exits; it does not change a running API worker.
The running API does not yet use this manager—ticket 15 owns serving integration.

Failed reloads raise `SnapshotLoadError` with a missing/corrupt/incompatible/stale reason.
`active.status()` atomically returns the retained snapshot and latest failure reason.
Existing readers keep their acquired reference; new candidate retrieval uses marked exact
fallback after a failed reload until a successful explicit reload clears the degraded state.

For N catalog ads and D=13 dimensions, export/vector preparation is O(N*D) work;
sorting IDs is O(N log N). Flat stores O(N*D) float32 data plus IDs. Build/load hold
serialized and native copies, with additional O(N*D) memory; validation scans every vector
and uses batches of at most 1,000. Flat search scans stored vectors, with candidate
selection/sorting overhead. These are algorithm costs, not benchmarks or a 100,000-ad claim.
Normalized inner-product behavior follows [FAISS metric documentation](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).

## Opt-in HNSW comparison

Flat remains the default build and intended initial serving option. To prepare one CPU
`IndexHNSWFlat` comparison, use the same dataset and vectors with an explicit opt-in:

```powershell
docker compose run --rm backend python -m app.retrieval.cli build --dataset-id $datasetId --output /artifacts/hnsw-v1 --index hnsw --hnsw-m 32 --ef-construction 200 --ef-search 128 --threads 1
docker compose run --rm backend python -m app.retrieval.cli load /artifacts/hnsw-v1 --interests technology gaming --limit 500 --ef-search 256 --threads 1
```

Local installed CLI equivalents use `uv run --locked adflow-index` from `backend/`.
HNSW arguments on a Flat build are rejected. A load-time `--ef-search` requires a cosine
query and an HNSW snapshot; it changes that query only. CLI JSON reports `hnsw_ef_search`
separately from the original persisted manifest. The common snapshot API accepts
`build_snapshot(..., hnsw=HnswSettings(...))`; omitting `hnsw` builds Flat.

| Setting | Default | Project bounds | Purpose |
| --- | --- | --- | --- |
| `m` / `--hnsw-m` | 32 | Integer 2–128 | Graph connectivity; base layer reserves 2*M neighbor slots |
| `ef_construction` / `--ef-construction` | 200 | Integer M–1,000,000 | Build exploration depth |
| `ef_search` / `--ef-search` | 128 | Integer 1–1,000,000 | Search exploration depth |
| `--threads` | 1 | Integer 1–64 | Offline process OpenMP threads; recorded at build |

These bounds are project validation choices, not measured tuning results. The pinned
builder uses bounded queues and relative-distance checks; runtime/build identity and
the builder version identify that fixed policy. Search creates a fresh native
`SearchParametersHNSW` for each call, so concurrent depth overrides do not modify the
shared graph. The pinned FAISS stubs omit this native parameter class and a few graph
attributes; one narrow suppression and a small protocol cover those verified native APIs.
See [FAISS HNSW settings](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes#indexhnsw-variants)
and [per-query parameters](https://github.com/facebookresearch/faiss/wiki/Setting-search-parameters-for-one-query).

`CurrentCandidateRetriever(session, active, ef_search=256)` uses a per-query override;
without it, the loaded manifest supplies the depth. Successful approximate retrieval
reports mode `hnsw`, its snapshot version and `hnsw_ef_search`. Both families share current
metadata filtering, expansion bounds and exact fallback. Fallback/empty-interest results
carry their fallback mode/reason and no nominal HNSW depth/index version. Flat rejects
HNSW-only overrides. Loading an HNSW snapshot for an explicit comparison does not promote
it or change API startup/serving defaults.

HNSW adds graph construction and memory to the same 13-dimensional float32 vectors.
FAISS describes roughly `4*D + 8*M` bytes per stored vector, before ID mapping, node/level
metadata, allocator/runtime and temporary build/load copies; actual artifact bytes and
memory must be recorded separately. Search explores a data-dependent graph; no universal
query complexity, speedup or full candidate coverage is promised. Highly duplicated/tied
vectors can leave too few approximate hits even with a high search depth, triggering the
same visible exact fallback. Tests allow interchangeable boundary members, then require
eligible distinct bounded candidates and consistent similarity/ID ordering.

Ticket 14 smoke evidence records actual small-data build/load/search times and artifact
sizes, not warmed latency distributions or a promotion result. Ticket 16 owns controlled
quality/cost comparisons and the 100,000-ad evidence. HNSW can replace the exact default
only after lower full-retrieval P95 and at least 95% canonical tie-aware recall are measured
on the declared query set, including fallback cost. IVF, compression and GPU remain deferred.

## Current-inventory candidate retrieval

`CurrentCandidateRetriever(session, active, search_limit=4000)` implements the public
`CandidateRetriever.retrieve(user, limit=500)` interface. It returns detached current
metadata for at most 500 distinct eligible ads. Callers own the PostgreSQL session and
transaction and pass configured limits explicitly; this adapter does not record recommendations.
Example after migrations, seeding and explicit snapshot preparation:

```python
from pathlib import Path
from uuid import UUID
from app.core.config import load_settings
from app.db.session import Database
from app.retrieval.contracts import RetrievalUser
from app.retrieval.current import CurrentCandidateRetriever
from app.retrieval.snapshots import ActiveSnapshot

settings = load_settings()
database = Database(settings)
active = ActiveSnapshot()
active.reload(Path("../artifacts/exact-local-v1"))
try:
    with database.session() as session:
        result = CurrentCandidateRetriever(
            session, active, search_limit=settings.retrieval_search_limit
        ).retrieve(
            RetrievalUser(id=1, dataset_id=UUID("<seed dataset UUID>"), interests=("technology",)),
            limit=settings.retrieval_candidate_limit,
        )
        print(result.model_dump_json())
finally:
    database.dispose()
```

Database triggers advance the revision transactionally for ad/advertiser inserts, edits and
deletes, including bulk SQL; rollbacks roll back revisions. No-op updates do not advance it.
Truncating either inventory table conservatively invalidates all catalog revisions. Advertiser
name edits also invalidate conservatively. Ordinary indexed retrieval reads the revision by
primary key before searching and again after metadata/filtering; it does not fingerprint or
scan all catalog rows to detect changes. Keep database triggers enabled and revision rows
database-managed. Restore/reseed operations require fresh artifacts.

An indexed query batch-fetches metadata for returned IDs with a typed PostgreSQL array
([SQLAlchemy ANY support](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.any_)),
so large configured expansions do not exhaust bind parameters. Missing, inactive and
wrong-dataset rows are excluded. Search doubles to the configured bound when filtering
shrinks results. A revision/dataset mismatch or mid-retrieval catalog change marks the
index stale. Missing/corrupt/incompatible reloads and insufficient filtered candidates also
use current eligible-inventory exact fallback, with explicit `fallback_reason` and no claimed
active index version. Fallback streams one PostgreSQL statement snapshot, scores every
eligible vector, and retains a bounded heap of candidates; it never rebuilds a serving index.
Empty interests use a bounded PostgreSQL bid-descending/ID-ascending query, with null cosine
scores. Zero eligible ads returns an empty successful result; database failures or invalid
current catalog data raise safe `WorkflowError(503, "retrieval_unavailable", ...)`.

`elapsed_ms` includes revision lookup, vector search, metadata, expansion and fallback.
`vector_elapsed_ms` times only index searches; `fallback_elapsed_ms` times the full fallback
query/scoring; `metadata_elapsed_ms` is the remaining metadata/orchestration time.
`searched_count` sums returned index hits across all queries (including repeats),
`expansion_count` counts additional queries, and `fallback_scanned_count` counts eligible
vectors scored in cosine fallback. It is zero for nonpersonalized SQL ordering; PostgreSQL
may still scan/sort eligible rows. Analyze fallback separately from nominal indexed latency.

Exact fallback costs O(N*D + N log K) time with O(K + B) candidate/streaming space for
eligible count N, candidate cap K and database fetch batch B=1000. Index expansion repeats
Flat scans or HNSW traversals and holds up to the configured bound of IDs in memory. Revision writes serialize
per dataset and offline export locks delay catalog commits; contention is a tradeoff to measure.
Default READ COMMITTED sessions observe committed changes between queries. Retrieval does
not lock selected ads: existing selection-time ad/advertiser locking and revalidation remain
mandatory. Phase 1 serving retains those protections; ticket 15 will integrate this adapter.
No ANN improvement, HNSW promotion, 100k-ad performance result or Phase 2 gate is claimed.

Focused checks from `backend/` with the isolated test database configured:

```powershell
$env:ADFLOW_RUN_POSTGRES_TESTS='1'
uv run --locked pytest tests/integration/test_candidate_retrieval.py tests/integration/test_index_catalog.py tests/unit/test_index_snapshots.py
```

Focused checks from `backend/` (PostgreSQL opt-in as above):

```powershell
uv run --locked pytest tests/unit/test_index_snapshots.py tests/unit/test_hnsw_snapshots.py tests/unit/test_index_cli.py tests/integration/test_index_catalog.py
uv run --locked mypy
```

Two sandboxed Windows pytest collections encountered intermittent native DLL initialization
errors (`0xc0000008`). Fresh-process import/persistence probes and repeated focused runs
outside that sandbox passed; native verification used the reviewed outside-sandbox path.
No dependency change or application workaround is attributed to a proven root cause.

## Reproducible retrieval component comparisons

`app.retrieval.benchmark.run_comparison(database, dataset_id, output, config)` and
`adflow-retrieval-benchmark` compare full-ad ranking, Flat plus ranking, and HNSW plus
the same `interest-overlap/baseline-v1` ranking. These are serial offline components,
with no HTTP calls, recommendation inserts, event writes, cache or CTR model. Their
component totals are not API latency, opportunities per second, or capacity evidence.
Full-ad ranking is a benchmark path, not a public recommendation query option.

Prepare migrations and synthetic entities explicitly in a separate test/benchmark
database. From `backend/`, after setting distinct application/test URLs:

```powershell
uv run --locked alembic -x database=test upgrade head
uv run --locked python -m app.seeding.cli --database test --seed 160016 --users 1000 --advertisers 200 --ads 100000 --append
# Use the dataset_id printed by the seed command. Choose a NEW output directory.
uv run --locked python -m app.retrieval.benchmark_cli --database test --dataset-id $datasetId --output ../artifacts/retrieval-comparison --queries 30 --empty-queries 3 --warmup-queries 10 --repetitions 3 --limit 500 --threads 1
```

The default query count is 100; the command above declares a shorter 30-query component
comparison. Query sampling is seeded and without replacement from available nonempty
profiles; reports record requested and actual counts. Empty-interest clones are explicit,
separate queries, never included in personalized recall/P95 or nominal ANN samples.
`--query-seed`, `--boundary-tolerance`, `--hnsw-m`, `--ef-construction`, `--ef-search`,
warmup and repetition controls are saved in the report. One FAISS thread and one serial
caller are the defaults. The runner restores its previous FAISS thread setting afterward.
Run it in its own process, rather than concurrently inside an API worker.

One repeatable-read PostgreSQL transaction freezes catalog eligibility, metadata and
profiles. A shared catalog revision lock also prevents catalog editors committing during
the comparison. This offline transaction disables its local idle timeout for index
preparation; serving timeouts are unchanged. Prefer the isolated benchmark database;
the CLI never seeds, migrates, resets, or deletes data. The optional application database
mode also holds this lock and is for deliberate offline comparisons.

Each new output directory retains `queries.json`, a compressed `catalog.jsonl.gz` export
with actual metadata/eligibility, complete immutable `flat/` and `hnsw/` artifacts,
`report.json` with raw per-query/repetition samples and summaries, and `status.json`.
An existing directory is refused. Failures/interruption leave a failed status and do
not claim a completed comparison. Inputs have checksums; code revision/source hashes,
dataset manifest/counts, query seed, catalog identity, runtime/hardware/database location,
index manifests/settings, build/reload/artifact sizes, process memory and CPU observations
are retained. No credentials are exported.

Build timings include native construction, serialization and artifact validation, outside
query timing. Process working-set/RSS observations and cumulative peaks include catalog,
reference scores, indexes and harness allocations; they are not isolated index memory
costs. Serialized index/artifact bytes are reported separately. Memory sampling is outside
component timings. CPU time includes measurement-loop quality evaluation/harness overhead.
The report distinguishes vector, metadata/filtering, exact fallback, ranking and component
total timings, plus modes, candidate counts, winners, bids, score differences and fallback
rates. Full-ad measurement materializes the baseline's required ID/interests/bid fields to
separate metadata and ranking timing, using O(N) harness memory; it is not the old streaming
selector's O(1) selection-memory implementation. Indexed paths use their actual metadata
retriever and rank at most C candidates. Totals include adapter work between stages.

Warmup samples and independent exact-score quality preparation are excluded from reported
latencies. Measured paths are deterministically interleaved for each query. Percentiles
use nearest rank on raw samples; per-repetition values are retained and never averaged
into a pooled P95. Repetitions reuse the same frozen inputs/artifacts/process, with no
database/cache reset. These short component repetitions do not replace Phase 8's
60-second warmup, three-minute HTTP runs or independent load-test repetitions.

Ordinary ID recall uses the exact Flat returned set and remains sensitive to boundary
ties. Canonical tie-aware recall uses all frozen eligible exact scores, with declared
absolute tolerance (default `1e-6`) around the kth score. It credits interchangeable
boundary members while separately counting missed strictly superior ads. For k=0, recall
is unavailable, not perfect. Reports retain query-level quality variation and differences
from the full-ad ranking winner; similarity recall does not guarantee preserving it.

HNSW eligibility requires lower full-retrieval P95 than Flat, every measured query's
tie-aware recall at least 95%, three repetitions and no personalized fallback. This is
a conservative quality gate. The runner never changes serving settings. If it fails,
retain Flat. Saved ticket-16 measurements and limitations are recorded in the
[comparison evidence](.scratch/adflow-implementation/evidence/ticket16/results.md).

Focused verification with the isolated PostgreSQL test database enabled:

```powershell
uv run --locked pytest tests/unit/test_retrieval_evaluation.py tests/unit/test_retrieval_benchmark_cli.py tests/integration/test_retrieval_benchmark.py
```

## Offline historical exposures

`python -m app.history.cli` (installed command `adflow-history`) generates separate
versioned training artifacts from an existing entity dataset. Default volume is 10,000
historical exposures; demo startup still generates none. From `backend/`, configure
distinct application/test URLs, prepare the chosen database explicitly, and use the
dataset ID printed by the seed:

```powershell
# Use a separate database for optional full preparation; preserve existing datasets.
uv run --locked alembic -x database=test upgrade head
uv run --locked python -m app.seeding.cli --database test --seed 180018 --users 10000 --advertisers 100 --ads 100000
uv run --locked python -m app.history.cli --database test --dataset-id $datasetId --output ../artifacts/history-demo --impressions 10000 --batch-size 1000 --seed 18
# Optional full history, in a NEW directory:
uv run --locked python -m app.history.cli --database test --dataset-id $datasetId --output ../artifacts/history-full --impressions 1000000 --batch-size 1000 --seed 18
```

`--database application` is an explicit alternative read source. Export uses a read-only
repeatable-read PostgreSQL transaction and releases it before generation. It freezes
all source user fields and eligible ad fields, including their advertiser ID/activity.
Only active ads belonging to active advertisers can be exposed. Missing datasets, users
or eligible inventory are errors. No recommendation/event/request-outcome tables are
written, and no serving API, ranking strategy, CTR model or index is called.

Each output directory contains `users.jsonl`, `ads.jsonl`, `exposures.jsonl` and a final
`manifest.json`. Exposures reference frozen user/ad IDs and contain a local integer
`impression_id`, UTC `impressed_at`, binary `clicked` and nullable `clicked_at`. The
identity is `(history_id, impression_id)`; local IDs restart in each history. Positive
click times follow their impressions, with at most one click per exposure. Clicks are
additional outcomes of the requested impression count, rather than a mixed event target.
The manifest retains dataset/entity provenance, versions, complete configuration, file
SHA-256 hashes, time range, stream derivations, observed synthetic CTR and matched versus
unmatched rates. Full source snapshots retain bids for provenance; bids are excluded
from the outcome calculation and future model inputs. Hidden preferences and generating
probabilities never appear in exposure rows or entity snapshots.

Outcome version `click-world-v1` uses the sigmoid of a logit with default intercept -4.2,
0.45 per distinct shared interest, 0.8 for category membership in the user's explicit
category preferences, mobile offset 0.15, tablet offset -0.1 and desktop/unknown offset 0.
Separate fixed hidden user/ad offsets each come from uniform [-0.15, 0.15]. These are
designed assumptions, not measured population statistics. The generator samples a
binary outcome; a relevant ad is never guaranteed a click. Outcome settings can be
supplied as an `OutcomeConfig` JSON file via `--outcome-config`; all defaults and overrides
are recorded. Do not change rules after viewing final-test or experiment results to
force an improvement. Synthetic rates do not establish real-user effectiveness.

Exposure samples users and eligible ads independently and uniformly with replacement,
after sorting IDs. Exposure, outcome, hidden-preference and click-delay randomness is
separate from entity-generation streams. Outcome draws derive from seed/version and
stable opportunity identity, making the public generator suitable for later live
simulation regardless of completion order. Batch size, bid and click delay do not
change the exposure or label stream. Same frozen inputs/configuration and supported
runtime reproduce files/manifest; changed entity snapshots or runtime have distinct
provenance. Regeneration uses a new output directory: existing outputs are refused.
On write failure, retained partial files carry `status.json` with `failed` and no
successful manifest is claimed. Consume only complete manifests with valid hashes.

Default simulated time starts at 2026-01-01 UTC, advances one second per exposure, and
uses click delays of 1–300 seconds. `--start`, `--interval-seconds` and
`--max-click-delay-seconds` override these controls. The manifest declares chronological
70/15/15 boundaries by `(impressed_at, impression_id)`; ticket 19 owns materializing
those splits and the shared five-feature builder. Labels stay with their impressions.
IDs, bids, variants, hidden preferences/probabilities and outcomes are not model features.
No preprocessing, training, final-test evaluation or live-data ingestion occurs here.

For U users, N eligible ads, H exposures and batch bound B, generation takes O(H) work
for fixed-width contexts plus O(U log U + N log N) source ordering and O(U+N+B) memory.
The frozen entity catalog stays in memory; history rows do not accumulate. Output disk
space grows with H. PostgreSQL export is streamed in 1,000-row batches before retaining
the entity snapshot. This bounds history memory without claiming constant catalog memory
or a hardware-independent full-generation duration.

Focused verification (isolated PostgreSQL opt-in enabled):

```powershell
uv run --locked pytest tests/unit/test_history_outcomes.py tests/unit/test_history_artifacts.py tests/unit/test_history_cli.py tests/integration/test_history.py
```

[Ticket 18's measured full run](.scratch/adflow-implementation/issues/18-synthetic-history.md)
used 10,000 users, 100 advertisers, 100,000 eligible ads and 1,000,000 exposures.
It produced 22,351 clicks (2.2351%); matched-interest rate was 3.6506%, unmatched 1.5299%.
The native runs took 119.88s and 122.37s and reproduced identical file hashes/manifests.
Each output occupied 195,766,408 bytes. Process-wide cumulative peak working set reached
374,382,592 bytes on the repeat; this includes the frozen catalog and is not isolated
batch memory. These are local Windows Python 3.10.11 offline costs, excluding entity
preparation, not a hardware-independent promise or serving-capacity result. Raw histories
remain under ignored `artifacts/history-ticket18-full/`; committed manifests, resource
observations and streaming audit results are under the ticket's evidence directory.

## Shared CTR features and chronological data splits

Prepare features from a complete historical artifact explicitly, from `backend/`:

```powershell
uv run --locked python -m app.ctr.dataset --history ../artifacts/history-demo --output ../artifacts/ctr-features-demo
uv run --locked pytest tests/unit/test_ctr_features.py tests/unit/test_ctr_dataset.py
```

`app.ctr.features.build_features(user, ad)` is the shared offline/serving builder.
`ctr-features-v1` contains exactly five raw fields: `shared_interest_count` (distinct
intersection of user interests and ad target interests), `category_match` (ad category
in user interests), `ad_category`, `device_type` (source `device`) and `age_group`.
Empty interests produce zero/false. Null, absent or empty categorical values become
the reserved string `__missing__`. Unseen nonempty categorical strings are preserved;
training-only fitted encoding with unknown handling belongs to the later persisted
model pipeline. No category vocabulary or numeric preprocessing is fitted here.

`write_feature_splits(history, output)` verifies source version/completion, all three
file hashes, snapshot counts, distinct identities, exposure references, chronological
click consistency and complete binary labels. It reads frozen `users.jsonl` and
`ads.jsonl`, never current database profiles. Each output row separates its five
`features` from `impression_id`, `impressed_at` and `label`. IDs, bid, experiment
variant, activity, country, category preferences, hidden probabilities, outcomes and
historical aggregates cannot become feature fields. Source files/provenance can
retain excluded fields; model inputs must select only the nested `features` object.

Rows are sorted by UTC impression time, then integer impression ID. The first
`floor(0.70*N)` rows are training, the next through `floor(0.85*N)` validation, and
the remainder final test. A late click stays with its impression's label. Small
datasets can have empty splits; the manifest records null boundaries for those
splits. Model training will separately require adequate class support.

Output contains `train.jsonl`, `validation.jsonl`, `test.jsonl` and a final complete
`manifest.json`, with `ctr-chronological-70-15-15-v1`, feature schema, counts/click
counts, first/last time/identity keys, exclusive row boundaries, output hashes and
source history/dataset identity, manifest hash, source hashes and generator configuration.
Existing output is refused. Failures after output creation retain `status.json`
without a complete manifest; use a new directory after fixing the input/filesystem.
CLI exit codes are 0 for success, 2 for rejected inputs/existing output and 3 for
filesystem/SQLite failure. The command needs neither database configuration nor
PostgreSQL access and never generates history or trains at startup.

Catalog memory is O(users + ads); exposures are processed one row at a time.
A temporary SQLite sort uses O(N) disk and O(N log N) sorting work, with an 8 MiB
page-cache target and file-backed temporary storage. This is not a total-process
memory cap. Temporary files are removed after closing the connection, including
on Windows. Keep enough free disk for the temporary database/sort and output.

## Offline CTR pipeline training

After feature preparation, train explicitly from `backend/` into a new directory:

```powershell
uv sync --locked
uv run --locked python -m app.ctr.training --features ../artifacts/ctr-features-demo --output ../artifacts/ctr-model-demo
uv run --locked pytest tests/unit/test_ctr_training.py
```

Optional `--config PATH.json` overrides `TrainingConfig`: `regularization` defaults
to `[0.1, 1.0, 10.0]` (1–8 positive, distinct, ascending C values), `seed` to 20,
`max_iter` to 1,000, and `tolerance` to `1e-6`. Smaller C means stronger L2
regularization. The `lbfgs` solver uses every training example with no class weights
or negative undersampling. One native numerical thread is used for repeatability.
The seed is recorded; `lbfgs` itself does not use randomized sample ordering.

The exported scikit-learn Pipeline contains a ColumnTransformer, followed by
LogisticRegression. StandardScaler fits the two numeric inputs (overlap count and
category-match flag); OneHotEncoder fits the three categoricals with
`handle_unknown="ignore"`. Missing strings come from the shared feature builder;
unseen categories encode as zeros in their respective learned categorical columns.
Only training data fits preprocessing and coefficients. Each declared C is fitted
on training data and scored using validation log loss; the lowest score wins, with
the smallest C breaking exact ties. The chosen fitted pipeline is exported without
refitting on validation or reading `test.jsonl`. Final-test metrics and baseline
comparisons belong to ticket 21. Validation loss is a selection statistic, not an
unbiased final evaluation or a promise of real-user effectiveness.

`app.ctr.inputs.feature_matrix` validates the shared builder's exact five fields and
orders them for pipeline prediction: overlap count, category match, ad category,
device type, age group. Labels, IDs, bid and other extra fields are rejected. Empty
batches form a `(0, 5)` matrix; the later serving adapter handles empty prediction
batches without calling scikit-learn. Current serving routes do not load this model.

Training requires complete compatible feature/split metadata and verifies both
consumed file hashes, counts, labels, references to distinct impression identities,
chronological order and first/last keys. Both training classes and nonempty
training/validation splits are required. Single-class validation uses explicit
binary labels for log loss. A convergence warning rejects the run, reporting C and
class counts with guidance to increase the iteration limit or inspect the inputs.
No unconverged candidate is silently selected. Existing output is refused. Failure
after output creation retains a failed status/reason without a complete manifest.
CLI codes: 0 success, 2 input/configuration/convergence rejection, 3 filesystem failure.

`pipeline.joblib` holds the entire fitted preprocessing/model pipeline. A complete
`manifest.json` records `ctr-logistic-v1`, a content-derived model ID, feature
schema/version/order, training/validation class counts, training base rate, solver
and candidate settings, convergence iterations, validation losses, source manifest
hash/full provenance and split identity, exact runtime/dependency versions, artifact
SHA-256, and a reload-checked prediction fixture (absolute tolerance `1e-12`).
Only project-produced local artifacts are intended for loading; checksum matching
does not establish trust. Later ticket 22 owns serving compatibility/activation.

Dependencies are pinned to scikit-learn 1.7.2, joblib 1.5.3, threadpoolctl 3.6.0 and
SciPy 1.15.3 below Python 3.14 / 1.16.3 on Python 3.14, alongside the existing NumPy
pins. scikit-learn 1.7.2 supports the project's Python 3.10–3.14 range; the native
and Docker runtimes are verified separately. Loading across dependency versions is
unsupported; prepare/train in the intended serving environment.
[Versioned installation guide](https://scikit-learn.org/1.7/install.html),
[1.7.2 release](https://github.com/scikit-learn/scikit-learn/releases/tag/1.7.2),
[ColumnTransformer](https://scikit-learn.org/1.7/modules/generated/sklearn.compose.ColumnTransformer.html),
[OneHotEncoder](https://scikit-learn.org/1.7/modules/generated/sklearn.preprocessing.OneHotEncoder.html),
[LogisticRegression](https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.LogisticRegression.html),
[persistence contract](https://scikit-learn.org/1.7/model_persistence.html).

Raw training/validation arrays, their identity set during validation, and encoded
training matrices use memory proportional to the consumed examples and encoded
feature count. History parsing is streamed into preallocated arrays, but fitting is
an in-memory offline operation. Candidate models run sequentially; each repeats
preprocessing and fitting. Sparse categorical output reduces practical storage;
it does not guarantee constant memory or a hardware-independent training duration.

## Frozen CTR probability evaluation

After explicit feature preparation and training, evaluate the frozen artifact from
`backend/`:

```powershell
uv sync --locked
uv run --locked python -m app.ctr.evaluation --features ../artifacts/ctr-features-demo --model ../artifacts/ctr-model-demo --output ../artifacts/ctr-evaluation-demo
uv run --locked pytest tests/unit/test_ctr_evaluation.py
```

Use the original feature directory and project-produced model in its original
training runtime. Evaluation checks model content identity, artifact checksum,
feature schema/order, source manifest identity, exact recorded Python/dependency
versions and the saved prediction fixture before scoring. Joblib is intended only
for trusted project artifacts; checksums do not establish trust. The pipeline loads
once and predicts one batch per split. No fitting, model selection, calibration
fitting, generator retuning or input/artifact mutation occurs during evaluation.
The training-only base rate comes from the frozen training manifest and is checked
against its recorded training counts. Evaluation does not reopen `train.jsonl`.

Both the model and constant baseline score identical validation and final-test
rows, retaining source hashes, chronological boundaries, counts, clicks and
observed CTR. Consumed split checksums, counts, binary labels and chronological
identities are validated. A bad input cannot publish a complete `report.json`.
Existing output directories are refused. CLI codes: 0 success, 2 input/model
rejection, 3 filesystem failure.

`report.json` records log loss (primary, lower is better), ROC-AUC (discrimination,
higher is better), Brier loss (lower is better), and full reliability bins for each
predictor/split. Explicit `[0,1]` labels preserve binary log loss on single-class
subsets; AUC is JSON `null` with a reason, and counts/Brier loss remain visible.
Binary Brier loss uses the mean squared probability error on the `[0,1]` scale.
Log loss uses scikit-learn's floating-point probability clipping, including at
zero/one. No accuracy headline or minimum score/lift is required.

`report.md` contains the comparison table and two `reliability-*.png` diagrams.
Matplotlib 3.10.8 renders them headlessly with a populated-range calibration panel
and a sample-count panel; plots retain synthetic-data limitations. `--bins` chooses
1–100 equal-width probability bins (default 20, declared before evaluation):
`[lower,upper)`, with 1 included in the final bin. Empty bins retain count zero and
null means in JSON and are omitted from the calibration curve. Sparse bins are
descriptive, not evidence of calibration precision. The count panel includes empty
bins and uses a nonnegative symlog axis so zero and large counts remain visible.

Probability scoring, discrimination and calibration differ: lower log loss alone
does not establish better calibration. Validation already influenced C selection;
the final test describes later outcomes in this designed synthetic world. Neither
proves real-user effectiveness or generalization to entirely unseen users/ads.
Keep unfavorable results visible and never retune the generator or fit anything
using final-test results. Future calibration work needs a separate development-data
plan. Evaluation reads each consumed split into memory and scores it as one batch;
memory scales with rows and encoded features, and reliability work is O(rows*bins).
These offline metrics are separate from serving latency or simulated revenue.

[Log loss](https://scikit-learn.org/1.7/modules/generated/sklearn.metrics.log_loss.html),
[Brier loss](https://scikit-learn.org/1.7/modules/generated/sklearn.metrics.brier_score_loss.html),
[probability calibration](https://scikit-learn.org/1.7/modules/calibration.html),
[Matplotlib 3.10.8](https://pypi.org/project/matplotlib/3.10.8/).

## CTR serving bundles and batch prediction

Package the frozen model and its exact evaluation before starting a serving
process. From `backend/`:

```powershell
uv run --locked python -m app.ctr.artifacts --model ../artifacts/ctr-model-demo --evaluation ../artifacts/ctr-evaluation-demo --output ../artifacts/ctr-serving-demo
$env:ADFLOW_CTR_MODEL_PATH='../artifacts/ctr-serving-demo'
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
uv run --locked pytest tests/unit/test_ctr_serving.py
```

The packaging command copies the complete fitted `pipeline.joblib` and creates a
content-identified `ctr-serving-bundle-v1` manifest. It retains the original model,
feature definitions, source/split provenance, parameters, exact runtime/dependency
versions, checksum, prediction fixture and evaluation report/metrics. Evaluation
must belong to the exact same model and original cohort counts/boundaries. No
training, recalibration or model selection occurs during packaging. Existing
output directories are refused. Treat completed bundle directories as immutable.
Use only trusted project-produced joblib artifacts; hashes detect accidental
changes and do not make arbitrary uploaded artifacts safe.

`ADFLOW_CTR_MODEL_PATH` is optional; empty means unconfigured. Application startup
loads and validates a configured bundle once per serving process/lifespan.
Validation checks bundle/model identities, pipeline checksum, schema/version/order,
evaluation association, exact recorded Python/dependency versions, binary class
labels and prediction-fixture agreement within `1e-12`. Offline evaluation uses
the same pipeline compatibility validator. Missing, corrupt or incompatible
models leave the adapter unavailable while baseline recommendations stay usable.
The database readiness contract is unchanged. Restart the process to activate a
different validated bundle; there is no automatic reload in the prediction loop.

`app.api.dependencies.get_ctr_model` supplies the process adapter to future ranking
consumers. `CTRModel.predict_batch(user, candidates)` takes detached profile/ad
mapping snapshots, builds the five shared features together, and makes one pipeline
call for the whole batch. `BatchPrediction` returns ad IDs/probabilities in input
order with model ID, model/feature versions and separate feature/inference times.
The adapter finds the positive column by label `1`, validates the binary label set,
and checks output count, finiteness, `[0,1]` bounds and row sums. `predict_one`
delegates to the batch path. Missing categorical fields and empty interests use
the shared builder's conventions; unseen categorical strings are accepted by the
persisted encoder. Empty batches return empty IDs/probabilities with zero measured
work, even without an available model; they do not call the pipeline.

Nonempty requests requiring the adapter raise typed `CTRUnavailable`, a
`WorkflowError` with HTTP status 503/code `ctr_unavailable`, for model load or
inference/output failures. The API's existing error handler provides a safe message
without internal paths or exception details. The current recommendation API still
uses the baseline; Phase 4 adds ranking strategies and CTR-dependent routes.
No baseline substitution or invented probabilities occur inside the CTR adapter.
Successful loaded adapters remain resident if their source files are removed;
source changes affect only a later startup/load.

The adapter has no database reads or per-candidate artifact loads. Feature/matrix
work uses O(candidate count * raw feature count) storage; model prediction depends
on encoded features and sparse matrix structure. Dense coefficient prediction is
O(candidate count * encoded feature count). Batch timings separate shared feature
building/validation/matrix construction from pipeline inference/output validation;
they exclude artifact loading, retrieval, database and HTTP work. No latency target
or speedup is assumed.

For Docker, prepare/train/evaluate/package inside the intended image runtime with
the existing `/artifacts` volume, then set
`ADFLOW_CTR_MODEL_PATH=/artifacts/ctr-serving-demo` and recreate the backend. Native
Windows Python 3.10 artifacts are rejected by the Python 3.12 container; retrain in
that runtime rather than modifying recorded versions. Build/check commands and
local `.env` use are described above.
[Persistence compatibility](https://scikit-learn.org/1.7/model_persistence.html) and
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

## Candidate-retrieval technical gate

[Ticket 17](.scratch/adflow-implementation/issues/17-retrieval-gate.md) records the
2026-10-08 gate commands and checks. The saved native comparisons used 1,000 and
100,000 eligible ads, limit 500, one FAISS thread/caller, and three component repetitions.
On the full dataset, Flat retrieval P95 was 40.715ms; the HNSW path including fallback
was 6631.704ms, with minimum query tie-aware recall 0.0 and 10% personalized fallback.
HNSW remains an explicit comparison option. Flat remains the default. The
[complete comparison](.scratch/adflow-implementation/evidence/ticket16/results.md)
includes separate empty-interest populations, memory/build costs, query variation,
and full-ad ranking. These saved observations are component evidence; this gate audits
them rather than claiming a fresh performance run or HTTP capacity result.

Flat still scans N indexed vectors: O(N*D) similarity work for D topic dimensions.
Its candidate set bounds downstream ranking to C <= 500 by default; this is distinct
from avoiding a catalog scan. Exact fallback scans current eligible inventory and
still bounds ranking to C. HNSW adds graph storage/build work and data-dependent search;
neither lower vector-only latency nor high mean recall establishes a better complete
pipeline. At 100,000 ads, even exact similarity retrieval changed the overlap-ranking
winner in 33 of 90 samples relative to full-ad ranking. Candidate recall and ranking
quality answer different questions.

Use the index preparation commands above to build a **new** immutable snapshot after
catalog, vocabulary or runtime changes, then explicitly restart/reload with its path.
Never reuse native Windows artifacts as compatible Linux artifacts. Until a compatible
snapshot is ready, missing/stale/corrupt/incompatible indexes use visible exact fallback
over current eligible ads; empty interests use bid/ID ordering without cosine scores.
There is no request-time rebuild. PostgreSQL failure remains 503.

The [retrieval learning checkpoint](.scratch/adflow-implementation/issues/58-learning-retrieval.md)
is now available and remains open. Explain why faster vector search alone does not
prove a better retrieval pipeline, then direct a small candidate-limit/search-depth
change and verify its candidate counts, tie-aware quality and cost. Phase 3 technical
work is unblocked; human understanding is recorded separately.

## Recommendation workflow

`app.services.recommendations.recommend(session, user_id, request_key)` implements
recommendation creation and replay. Use a fresh session from `database.session()`;
the service owns its transaction and commits before returning a `RecommendationResult`.
It returns the saved ID, creation time, user and immutable `AdSelection`, or a result
with both recommendation ID and selection `None` for no ad. Selection does not create
an impression. HTTP routes and the event workflow are described below.

Request keys contain 1–255 characters and cannot be blank. Keys are preserved exactly
and are globally unique. Within 24 hours, the same key/user returns its saved selection
or no-ad outcome without reranking, even after inventory/profile edits. Another user
gets `WorkflowError` with status 409; ownership is checked before expiry. At or after
creation plus 24 hours, reuse returns 410 and requires a fresh key. Unknown users get
404. Invalid keys get 422. Required database reads, writes, commit errors and pool/lock
timeouts get a safe 503; API adapters translate these workflow statuses into HTTP responses.

The service retrieves only ads in the user's dataset, respecting the existing composite
foreign keys that prevent cross-dataset recommendations. It ranks at most
`ADFLOW_RETRIEVAL_CANDIDATE_LIMIT` candidates (default/max 500), using distinct shared
interests, then bid, then ascending ID. Retrieval similarity determines membership,
not the ranking score; limiting membership can change the full-catalog winner.
The user profile is share-locked for a new decision. After selection, the service
share-locks the chosen ad and advertiser, rechecks activity, bid, target interests,
category and advertiser identity,
then snapshots the locked payload and distinct overlap score together. A changed winner
restarts the transaction/retrieval, up to three attempts; sustained changes yield retryable
503. Other ads may change during a scan; this is coherent winner revalidation, not a
serializable snapshot of all inventory.

Selected ad payloads include decimal bid (stored as a JSON string), overlap score and
meaning, strategy `interest-overlap`, version `baseline-v1` and null predicted CTR.
New selections also retain a compact `retrieval` object with mode, snapshot/vector identity,
requested/returned counts, fallback reason, expansion/scanned counters and retrieval timings.
Candidate payloads are omitted. Existing pre-integration selections replay with null retrieval
context. Replay never retrieves or ranks, even after an index swap or load failure.
The recommendation bid column and JSON snapshot come from the same decision, with one
server UTC creation time shared by the recommendation and key. Replay reads this
durable payload, never the current ad. The optional callable `clock` is a server-side
test seam; clients cannot supply timestamps. Replay expiry uses receipt time captured
once on entering the service, including uniqueness recovery.

PostgreSQL request-key uniqueness is the concurrency authority. A losing insert rolls
back the entire transaction, including any newly inserted recommendation, before reading
the winner in a new transaction. Only the request-key primary-key violation is treated
as a replay race; other database failures become 503. A response lost after commit is
safe to retry with the same key. No history cleanup or key recycling is performed.

New decisions add bounded ranking to retrieval and indexed user/key/snapshot lookups,
bounded revalidation and two inserts (one for no-ad). Replays use indexed durable
lookups and no inventory scan. Missing/stale/unusable indexes may require exact retrieval
over all eligible ads; limiting ranking does not eliminate that scan. History grows with opportunities; no performance claim
is made. Row locks can delay inventory editors; configured lock/statement timeouts bound
database waits, not an end-to-end request deadline. This follows
[SQLAlchemy transaction contexts](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
and [PostgreSQL row locks](https://www.postgresql.org/docs/18/explicit-locking.html).

Set `ADFLOW_RETRIEVAL_INDEX_PATH` to a prepared immutable snapshot directory to load it
at application startup. Leave it unset/empty for exact current-inventory fallback. In
Compose, use a path under `/artifacts`, where the existing artifact volume is mounted.
For example, after the offline build commands above, set it to `/artifacts/exact-v1` and
recreate the backend. No index is built during startup or requests. Flat is the initial
default; loading an HNSW artifact is an explicit comparison, not a measured promotion.
Missing, corrupt or incompatible startup artifacts keep serving through visibly marked
fallback. A stale dataset/catalog likewise falls back on each request until rebuilt.
Each process owns `app.state.snapshots`, an `ActiveSnapshot`; controlled in-process
reload uses its validated `reload(path)` interface. There is no HTTP reload endpoint
or automatic filesystem watcher. A failed reload retains the old reference but marks
retrieval degraded; a successful reload clears that failure. Each worker must load its
own replacement. Direct service callers can pass `snapshots`, `candidate_limit` and
`search_limit`; omitted snapshots use exact fallback. No CTR model is required.

Focused serving checks from `backend/` with the isolated test database configured:

```powershell
uv run --locked pytest tests/integration/test_retrieval_serving.py tests/integration/test_recommendations.py
```

With the isolated test database configured, focused verification from `backend/`:

```powershell
$env:ADFLOW_RUN_POSTGRES_TESTS = "1"
uv run --locked pytest tests/integration/test_recommendations.py
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
```

These tests append unique fixtures to the dedicated test database. They coordinate real
concurrent requests and inventory edits, and create temporary test-only triggers to
reject inserts or commits; those triggers are removed in `finally` blocks. No database
reset or durable-history deletion occurs. Run integration checks serially.

## Impression and click workflow

`app.services.events.record_event(session, recommendation_id, event_type)` accepts
`"impression"` or `"click"` and returns an immutable `EventResult` after commit. As with
recommendations, supply a fresh session from `database.session()`; the service owns the
transaction. The result contains recommendation ID, event type, server receipt time,
stored user/ad attribution and decimal simulated revenue. Clients provide no user/ad,
bid or revenue claims. HTTP endpoints validate UUIDs and map responses as described below.

Only explicit display confirmation records an impression. A first click needs a
committed impression; otherwise `WorkflowError` reports 409 with `impression_required`,
allowing confirmation followed by retry. A first event is accepted strictly before the
recommendation's creation time plus 24 hours; exactly at that boundary and later return
410. Unknown recommendation IDs return 404. An accepted duplicate is checked before
expiration and returns the original event, including timestamp/revenue, even after the
window closes. Database read/write/commit or pool/lock failures return a safe 503.

Each impression stores zero revenue. Each first accepted click stores the recommendation's
captured bid in its event row, so event acceptance and simulated revenue are one atomic
insert. Zero bids still accept clicks with zero credit. Later bid edits or ad/advertiser
deactivation affect neither attribution nor eligibility of this saved recommendation.
Separate recommendations of the same ad can each receive their own impression and click.
Summing accepted click rows provides simulated revenue without a second mutable counter.

The `(recommendation_id, event_type)` primary key is the concurrency authority. After
prechecks, `INSERT ... ON CONFLICT (recommendation_id, event_type) DO NOTHING` suppresses
only a duplicate of that event identity. A racing insert waits for the other transaction,
then reads the committed winner under PostgreSQL's default READ COMMITTED isolation.
No existing event is updated and no additional credit is applied. An impression still
in flight may cause a simultaneous click to return 409; retry the click after confirmation
commits. A response lost after commit is safe to retry. Required failures never report
an unsaved acceptance. This follows
[SQLAlchemy PostgreSQL conflict handling](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)
and [PostgreSQL INSERT](https://www.postgresql.org/docs/18/sql-insert.html).

`app.core.clock.utc_now` supplies server UTC time to both workflows. The event service
captures receipt time once before database work; its optional callable `clock` supports
controlled tests and is not a client timestamp field. Event processing uses a constant
number of indexed recommendation/event lookups and at most one inserted event, with
O(1) application working space. Index maintenance and contended insert waits add cost;
configured timeouts bound database waits, not an end-to-end request deadline. Durable
event history grows with accepted interactions; no pruning or throughput claim is added.

Focused checks from `backend/`, with the dedicated PostgreSQL test URL configured:

```powershell
$env:ADFLOW_RUN_POSTGRES_TESTS = "1"
uv run --locked pytest tests/integration/test_events.py
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
```

Tests create unique synthetic datasets/opportunities, coordinate concurrent duplicates,
and install fixture-specific insert/commit failure triggers removed in `finally` blocks.
They verify event counts and decimal revenue directly at the PostgreSQL persistence
boundary without clearing existing history. Run integration checks serially.

## HTTP lifecycle and health

With migrations and seed preparation complete, use either the Compose API or local
Uvicorn. Run from the repository root in another PowerShell terminal. Query an actual
seeded user from the active database, so its ID works regardless of the seed runtime:

```powershell
$userId = [long](docker compose exec -T postgres psql -U adflow -d adflow -Atc 'SELECT id FROM users ORDER BY id LIMIT 1')
$api = 'http://127.0.0.1:8000'
$headers = @{ 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$body = @{ user_id = $userId } | ConvertTo-Json
$recommendation = Invoke-RestMethod -Method Post -Uri "$api/api/v1/recommendations" -Headers $headers -ContentType 'application/json' -Body $body
$replay = Invoke-RestMethod -Method Post -Uri "$api/api/v1/recommendations" -Headers $headers -ContentType 'application/json' -Body $body
$eventBody = @{ recommendation_id = $recommendation.recommendation_id } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/api/v1/events/impression" -ContentType 'application/json' -Body $eventBody
Invoke-RestMethod -Method Post -Uri "$api/api/v1/events/click" -ContentType 'application/json' -Body $eventBody
Invoke-RestMethod -Method Post -Uri "$api/api/v1/events/click" -ContentType 'application/json' -Body $eventBody
Invoke-RestMethod -Uri "$api/health/live"
Invoke-RestMethod -Uri "$api/health/ready"
```

For native PostgreSQL, replace the first command with the equivalent `psql` query using
your configured host/account/database. The walkthrough creates one recommendation, one
impression and one click. Inspect counts and captured-bid credit from the repository root:

```powershell
$id = $recommendation.recommendation_id
docker compose exec -T postgres psql -U adflow -d adflow -c "SELECT event_type, count(*), sum(simulated_revenue) FROM events WHERE recommendation_id = '$id' GROUP BY event_type ORDER BY event_type"
```

Both counts must be one; the click total must equal `selection.bid`, and impression
revenue must be zero. Retries return the same recommendation/event without extra credit.

The recommendation response contains `recommendation_id`, `user_id`, `created_at`, and
`selection` (the saved ad payload, decimal bid, overlap score and strategy identity).
The baseline's `predicted_ctr` is null. Reusing the key replays the saved response.
With no eligible ad, the response is 204 with an empty body; handle this before sending
events. Event responses contain `recommendation_id`, `event_type`, server-derived
`user_id`/`ad_id`, the original event `created_at`, and decimal `simulated_revenue` as a
JSON string. Duplicate clicks return the same acceptance and add no credit.

| Response | Meaning |
| --- | --- |
| 200 | Saved selection/replay or accepted/duplicate event |
| 204 | Saved no-ad outcome/replay; no recommendation or event |
| 404 | Unknown user/recommendation |
| 409 | Key belongs to another user, or click requires impression confirmation |
| 410 | Request key expired, or first event received after expiry |
| 422 | Missing/malformed body/header; positive signed 64-bit user ID and UUID required |
| 503 | Required durable storage unavailable or repeatedly changing inventory |

Bodies reject extra fields, including client attribution and timestamps. User IDs must
be JSON integers. Provide exactly one nonblank `Idempotency-Key`, at most 255 characters;
its exact value is preserved for replay. Error bodies use
`{"error":{"code":"impression_required","message":"Confirm the impression before retrying the click"}}`.
Validation errors return `invalid_request` (or `invalid_request_key`) without echoing input.
Unexpected application failures return a safe 500 `internal_error`. Every HTTP response
includes a server-generated `X-Request-ID`.

`/health/live` performs no database work. `/health/ready` executes `SELECT 1` through the
bounded pool and returns 503 on connectivity failure. It checks reachability; migrations
remain an explicit setup check.

Application logger `adflow.requests` emits one JSON INFO record per request with request
ID, route template, method, status and duration in milliseconds. Validated workflow
context adds user/recommendation/ad IDs, outcome, strategy and overlap score where
available. Request keys appear only as SHA-256 digests. Raw headers, bodies, query strings,
ad payloads, database exception text and credentials are excluded. Fixed stage hooks
measure `selection_ms`, `recommendation_ms`, `event_ms` or `database_probe_ms` where run;
replays skip selection. Workflow timers include commit time. Request duration ends when
response headers are prepared; it is not client-observed network latency. Timings are
bounded request-local data, with no metric history or telemetry platform. New decisions
also report `retrieval_ms` (including `vector_ms`, `metadata_ms`, `fallback_ms`),
`ranking_ms`, and `database_ms` for lifecycle key/profile/winner queries, flushes and
commit, excluding retrieval's database work (already included in metadata/fallback).
Retry work accumulates in request timings; saved retrieval timings describe the final
selection attempt. These nested timers must not all be added together as disjoint costs.

Focused checks from `backend/`:

```powershell
uv run --locked pytest tests/unit/test_http.py
$env:ADFLOW_RUN_POSTGRES_TESTS = '1'
uv run --locked pytest tests/integration/test_http_lifecycle.py
uv run --locked pytest tests/integration/test_http_resilience.py
Remove-Item Env:ADFLOW_RUN_POSTGRES_TESTS
```

The resilience suite uses the production app lifespan and session dependencies with its
application URL explicitly set to `TEST_DATABASE_URL`; its companion URL names an unused
database. Neither URL targets development. It overrides only the server-owned `get_clock`
dependency, so exact UTC expiry checks do not need sleeps or client timestamps. The clock
is passed into both services; normal requests continue to use `utc_now`.

Tests simulate a failed response send after selection commits, then replay the saved ad
after bid/profile/eligibility edits. Concurrent HTTP tests hold a user-row or event-table
lock and observe four blocked PostgreSQL transactions before releasing them. A two-second
gate deadline and finite database waits bound synchronization; the small polling delay
does not establish ordering. Insert/commit failures use uniquely named triggers scoped to
one request key or recommendation/event pair, removed in `finally`. Assertions verify
durable counts and decimal credit, including zero bids and expired accepted duplicates.
Run integration tests serially against a dedicated test database. Fixtures append unique
datasets; they never reset, truncate or delete development history. These scenarios verify
correctness, with no throughput or latency claim. Mechanisms follow official
[FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
and [PostgreSQL locking](https://www.postgresql.org/docs/18/explicit-locking.html).

HTTP validation/error adapters follow the official
[FastAPI error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/) and
[response status documentation](https://fastapi.tiangolo.com/tutorial/response-status-code/).
No dependency versions changed for ticket 07.

## Persistence contract

`datasets` records identity, seed, generator version and JSON configuration. Users,
advertisers and ads reference it; composite foreign keys prevent cross-dataset ads and
recommendations. Recommendation snapshots retain the original ad payload and bid. Ads
and advertiser eligibility may change without changing saved recommendations.

Request keys are globally unique and identify an immutable outcome. A null recommendation
represents no ad; a selected recommendation can belong to only one outcome, for the same
user. Events use `(recommendation_id, event_type)` as their primary key. Only impressions
and clicks are allowed. Monetary fields use `NUMERIC(12,4)` and Python `Decimal`, reject
negative/NaN values, and support zero bids. Impression revenue must be zero; click revenue
is stored on the click itself so acceptance and its credit can be one atomic insert.

All lifecycle times use PostgreSQL `timestamptz`, with connections configured for UTC.
Database triggers reject updates, deletes and truncation of datasets, request outcomes,
recommendations and events. This preserves snapshot/provenance, expiration identity and
deduplication history. No cascading delete or automatic cleanup exists. Database owners
can still explicitly change schema/disable triggers; these are application persistence
guarantees, not an administrative access boundary.

Use `with database.transaction() as session:` for a single atomic unit: success commits,
exceptions (including commit failures) roll back, and cleanup returns the connection.
For request dependencies, `get_session` supplies `database.session()`; services must use
`with session.begin():` and finish committing before returning success. Dependency teardown
rolls back unfinished work and never commits after sending a response. Catch a uniqueness
conflict outside the failed transaction and read the winner in a new transaction, or use
an explicit SQLAlchemy savepoint when retaining a surrounding transaction is necessary.

Workflow services in tickets 05/06 enforce event ordering, 24-hour receipt eligibility,
the selected bid as click credit, complete snapshot payloads and atomic recommendation/
outcome creation. Schema constraints supply identity, type, amount and reference integrity;
the workflow behavior is not implemented here. Primary/unique/FK lookup indexes avoid
application-only deduplication; no throughput claim is made.

## Module boundaries

| Module | Purpose |
| --- | --- |
| `backend/app/main.py` | Factory and lifespan; creates/disposes a lazy database pool per app |
| `backend/app/core/config.py` | Environment loading, safe validation, connection limits |
| `backend/app/api/dependencies.py` | Synchronous settings/database/session request dependencies |
| `backend/app/api/routes.py` and `backend/app/schemas/` | Thin validated lifecycle/health routes and public response contracts |
| `backend/app/core/observability.py` | JSON request logger and bounded request-local stage timing hooks |
| `backend/app/db/session.py` | Bounded PostgreSQL engine, sessions, atomic transaction contexts |
| `backend/app/models/records.py` | Typed dataset, user, advertiser, ad, outcome, recommendation and event records |
| `backend/alembic.ini` and `backend/migrations/` | Explicit versioned schema and immutable-history triggers |
| `backend/tests/unit/test_config.py` | Configuration loading, isolation, validation, secret redaction |
| `backend/tests/unit/test_app.py` | Factory and synchronous dependency behavior through TestClient |
| `backend/tests/integration/` | Opt-in PostgreSQL constraints, snapshots, rollback, and wait limits |
| `backend/app/seeding/` | Versioned entity generator, atomic append/no-op persistence, seed CLI |
| `backend/app/history/` | Independent outcomes, read-only frozen source export, bounded offline history writer and CLI |
| `backend/app/core/topics.py` and `backend/app/retrieval/` | Shared ordered vocabulary, normalized membership vectors, validated candidate-retrieval contracts and limits |
| `backend/app/db/catalog.py` and `backend/app/retrieval/snapshots.py`, `cli.py` | Offline eligible catalog export, immutable Flat/HNSW artifacts, validated process-local reload and explicit CLI |
| `backend/app/retrieval/current.py` | Current metadata filtering, bounded expansion, revision checks and marked exact/nonpersonalized fallback |
| `backend/app/ranking/` and `backend/app/db/selection.py` | Pure deterministic baseline and streamed eligible-inventory reader |
| `backend/app/services/recommendations.py` and `backend/app/core/errors.py` | Atomic recommendation/no-ad opportunities, durable replay and safe workflow failures |
| `backend/app/services/events.py` and `backend/app/core/clock.py` | Idempotent client events, captured-bid credit and shared server UTC clock |
| `backend/tests/unit/test_seed_generation.py` and `test_seed_cli.py` | Reproducibility, stream independence, validation and CLI checks |
| `backend/pyproject.toml` | Package, dependency ranges, pytest, Ruff, strict mypy configuration |
| `backend/uv.lock` | Reproducible resolved dependency versions |
| `backend/Dockerfile` and `backend/.dockerignore` | Locked runtime image, non-root API startup, health check and filtered build context |
| `docker-compose.yml` | Local backend/PostgreSQL services, loopback ports, persistent volume and dependency health ordering |

The approved layout adds remaining subsystems when their
implementation tickets begin. Empty subsystem
placeholders are deliberately deferred according to the Phase 1 boundary decision.

Dependency choices were checked against primary sources on 2026-10-07:
[FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[SQLAlchemy URL configuration](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls),
and [uv locking](https://docs.astral.sh/uv/concepts/projects/sync/).
Persistence follows [SQLAlchemy transaction contexts](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html),
[Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[PostgreSQL timeouts](https://www.postgresql.org/docs/18/runtime-config-client.html), and
[psycopg binary installation](https://www.psycopg.org/psycopg3/docs/basic/install.html).
The installed Starlette 1.7.0 package metadata specifies `httpx2` for TestClient;
the lock resolves FastAPI 0.142.4, Pydantic 2.13.5, pydantic-settings 2.15.0,
SQLAlchemy 2.0.54, Alembic 1.20.0, psycopg 3.3.6, Uvicorn 0.54.0, and httpx2 2.13.1.
Compatibility evidence is the
local import, tests, type/lint checks, and wheel build, rather than version ranges alone.
