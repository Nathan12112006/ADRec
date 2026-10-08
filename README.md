# AdFlow

A personalized advertising recommendation demo using synthetic data. Ticket 01 supplies
the backend package and configuration foundation. Recommendation/event APIs, database
sessions and migrations, health checks, seeds, and Docker packaging arrive in later tickets.

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
Startup does not connect to a database or create tables. Stop the server with Ctrl+C.

`uv.lock` pins the entire dependency graph, including development and build dependencies;
`--locked` rejects stale project metadata. Dependency updates must deliberately regenerate
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
| `DB_POOL_SIZE` | 5 | Integer, 1–20 connections |
| `DB_MAX_OVERFLOW` | 5 | Integer, 0–20 additional connections |

Database URLs use `postgresql+psycopg://user:password@host:port/database`. URL-encode
special characters in credentials. Query options are rejected so alternate hosts/database
names and timeout overrides cannot bypass configuration checks. Database names must differ
even across hosts, credentials, and encoded names. This is a configuration guard, not proof
of database permissions or runtime connectivity. The database adapter in ticket 02 must
apply these pool/connection limits; structured logging is ticket 07. Set server log verbosity
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
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv build
```

The unit tests use no PostgreSQL connection and never reset a database. TestClient exercises
the real ASGI app and synchronous request dependencies in process. On this Codex Windows
host, TestClient's event loop requires running outside the execution sandbox; normal local
execution works. Future PostgreSQL integration tests must explicitly target the isolated
test URL. No integration/Docker verification is claimed for this ticket.

## Module boundaries

| Module | Purpose |
| --- | --- |
| `backend/app/main.py` | Factory; creates independent apps with injected or loaded settings |
| `backend/app/core/config.py` | Environment loading, safe validation, connection limits |
| `backend/app/api/dependencies.py` | Synchronous request-scoped settings dependency |
| `backend/tests/unit/test_config.py` | Configuration loading, isolation, validation, secret redaction |
| `backend/tests/unit/test_app.py` | Factory and synchronous dependency behavior through TestClient |
| `backend/pyproject.toml` | Package, dependency ranges, pytest, Ruff, strict mypy configuration |
| `backend/uv.lock` | Reproducible resolved dependency versions |

The approved layout adds `app/db`, `models`, `schemas`, `services`, `ranking`, `migrations`,
`scripts`, and `tests/integration` when their implementation tickets begin. Empty subsystem
placeholders are deliberately deferred according to the Phase 1 boundary decision.

Dependency choices were checked against primary sources on 2026-10-07:
[FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[SQLAlchemy URL configuration](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls),
and [uv locking](https://docs.astral.sh/uv/concepts/projects/sync/).
The installed Starlette 1.7.0 package metadata specifies `httpx2` for TestClient;
the lock resolves FastAPI 0.142.4, Pydantic 2.13.5, pydantic-settings 2.15.0,
SQLAlchemy 2.0.54, Uvicorn 0.54.0, and httpx2 2.13.1. Compatibility evidence is the
local import, tests, type/lint checks, and wheel build, rather than version ranges alone.
