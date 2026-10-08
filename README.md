# AdFlow

A personalized advertising recommendation demo using synthetic data. Ticket 01 supplies
the backend package and configuration foundation. Ticket 02 adds synchronous PostgreSQL
sessions and explicit Alembic migrations. Ticket 03 adds reproducible entity seeding.
Recommendation/event APIs, health checks,
and Docker packaging arrive in later tickets.

## Install and run locally

Verified on Windows with CPython 3.10.11 and uv 0.12.23. The package declares Python
3.10–3.14; other runtimes/platforms have not yet been exercised. Run from the repository root
in PowerShell (the `uv` commands also work in other shells):

```powershell
python -m pip install uv==0.12.23
Copy-Item .env.example .env
Set-Location backend
uv sync --locked
uv run --locked python -c "from app.main import create_app; create_app(); print('configuration valid')"
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Open [Swagger UI](http://127.0.0.1:8000/docs) or
[OpenAPI](http://127.0.0.1:8000/openapi.json). No business endpoints exist yet. Importing
`app.main` alone needs no configuration; calling `create_app()` validates configuration.
Startup creates a lazy connection pool, without connecting or creating tables. Shutdown
disposes the pool. Stop the server with Ctrl+C. Set up the database explicitly below before
using database-backed functionality added by subsequent tickets.

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

Database URLs use `postgresql+psycopg://user:password@host:port/database`. URL-encode
special characters in credentials. Query options are rejected so alternate hosts/database
names and timeout overrides cannot bypass configuration checks. Database names must differ
even across hosts, credentials, and encoded names. This is a configuration guard, not proof
of database permissions or runtime connectivity. The database adapter applies these limits,
sets the connection timezone to UTC, and disconnects sessions left idle in a transaction for
30 seconds. Statement timeouts bound server execution, not an end-to-end HTTP deadline.
Structured logging is ticket 07. Set server log verbosity
with Uvicorn's `--log-level` option until application logging is implemented.

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

The unit tests use no PostgreSQL connection. TestClient exercises
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

This includes all unit and PostgreSQL tests. PostgreSQL 18.6 was verified locally using
official [EDB portable binaries](https://www.enterprisedb.com/download-postgresql-binaries)
after Docker Desktop failed to start. Docker packaging/startup is not yet verified.

## PostgreSQL setup and migrations

Use a PostgreSQL server you control with separate development and test databases. The
example `.env` targets port 5432. With Docker Desktop running, this optional local server
setup matches those credentials (run from the repository root):

```powershell
docker run --detach --name adflow-postgres --publish 127.0.0.1:5432:5432 --env POSTGRES_USER=adflow --env POSTGRES_PASSWORD=adflow --env POSTGRES_DB=adflow postgres:18
docker exec adflow-postgres pg_isready -U adflow -d adflow
docker exec adflow-postgres createdb -U adflow adflow_test
```

Wait until `pg_isready` succeeds before creating the test database. With a native server,
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
the schema and revision `0002` protects durable history. Downgrades are intentionally
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

## Recommendation workflow

`app.services.recommendations.recommend(session, user_id, request_key)` implements
recommendation creation and replay. Use a fresh session from `database.session()`;
the service owns its transaction and commits before returning a `RecommendationResult`.
It returns the saved ID, creation time, user and immutable `AdSelection`, or a result
with both recommendation ID and selection `None` for no ad. Selection does not create
an impression. HTTP routes and event workflows are later tickets 07 and 06.

Request keys contain 1–255 characters and cannot be blank. Keys are preserved exactly
and are globally unique. Within 24 hours, the same key/user returns its saved selection
or no-ad outcome without reranking, even after inventory/profile edits. Another user
gets `WorkflowError` with status 409; ownership is checked before expiry. At or after
creation plus 24 hours, reuse returns 410 and requires a fresh key. Unknown users get
404. Invalid keys get 422. Required database reads, writes, commit errors and pool/lock
timeouts get a safe 503; API adapters will translate these workflow statuses in ticket 07.

The service scans only ads in the user's dataset, respecting the existing composite
foreign keys that prevent cross-dataset recommendations. The inventory reader accepts
an optional `dataset_id`; its original unrestricted selector interface remains available.
The user profile is share-locked for a new decision. After selection, the service
share-locks the chosen ad and advertiser, rechecks activity, bid and target interests,
then snapshots the locked payload and distinct overlap score together. A changed winner
restarts the transaction/scan, up to three attempts; sustained changes yield retryable
503. Other ads may change during a scan; this is coherent winner revalidation, not a
serializable snapshot of all inventory.

Selected ad payloads include decimal bid (stored as a JSON string), overlap score and
meaning, strategy `interest-overlap`, version `baseline-v1` and null predicted CTR.
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

New decisions retain the baseline scan costs and add indexed user/key/snapshot lookups,
bounded revalidation and two inserts (one for no-ad). Replays use indexed durable
lookups and no inventory scan. History grows with opportunities; no performance claim
is made. Row locks can delay inventory editors; configured lock/statement timeouts bound
database waits, not an end-to-end request deadline. This follows
[SQLAlchemy transaction contexts](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
and [PostgreSQL row locks](https://www.postgresql.org/docs/18/explicit-locking.html).

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
| `backend/app/db/session.py` | Bounded PostgreSQL engine, sessions, atomic transaction contexts |
| `backend/app/models/records.py` | Typed dataset, user, advertiser, ad, outcome, recommendation and event records |
| `backend/alembic.ini` and `backend/migrations/` | Explicit versioned schema and immutable-history triggers |
| `backend/tests/unit/test_config.py` | Configuration loading, isolation, validation, secret redaction |
| `backend/tests/unit/test_app.py` | Factory and synchronous dependency behavior through TestClient |
| `backend/tests/integration/` | Opt-in PostgreSQL constraints, snapshots, rollback, and wait limits |
| `backend/app/seeding/` | Versioned entity generator, atomic append/no-op persistence, seed CLI |
| `backend/app/ranking/` and `backend/app/db/selection.py` | Pure deterministic baseline and streamed eligible-inventory reader |
| `backend/app/services/recommendations.py` and `backend/app/core/errors.py` | Atomic recommendation/no-ad opportunities, durable replay and safe workflow failures |
| `backend/tests/unit/test_seed_generation.py` and `test_seed_cli.py` | Reproducibility, stream independence, validation and CLI checks |
| `backend/pyproject.toml` | Package, dependency ranges, pytest, Ruff, strict mypy configuration |
| `backend/uv.lock` | Reproducible resolved dependency versions |

The approved layout adds `schemas`, `services`, `ranking` and `scripts` when their
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
