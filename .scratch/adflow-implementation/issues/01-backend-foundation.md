# 01 — Create the backend package and configuration foundation

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 1 — Core backend
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: none

## Scope

Create the approved backend package layout and FastAPI application factory with synchronous dependency seams. Configure environment-based application/test database URLs, log level and bounded connection settings; add .env.example, ignore rules, reproducible dependency configuration, pytest/TestClient and Python lint/type commands. Select compatible versions against primary sources at implementation time.

## Dependencies

No prerequisites. This is the first implementation ticket.

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] The app imports and configuration validation reports missing/invalid settings without leaking credentials.
- [x] Application and test database settings are distinct; relevant setup/config checks and lint/type commands run.
- [x] Document exact local install/run/check commands and the purpose of each module.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.



### Implementation evidence — 2026-10-07

Implemented by Codex. Added `backend/pyproject.toml`, `backend/uv.lock`, application package initialization, `app/main.py`, `app/core/config.py`, `app/api/dependencies.py`, configuration/factory unit tests, root `.env.example`, `.gitignore`, and `README.md`.

The synchronous FastAPI factory accepts explicitly validated settings or loads environment/root dotenv settings. Imports perform no configuration or database I/O. URLs are secret fields; environment diagnostics report only field locations/error codes. PostgreSQL psycopg URL validation rejects malformed URLs and query overrides; distinct decoded database names guard application/test isolation even with host aliases. Connection/pool waits and pool capacities have finite validated bounds. Their use by SQLAlchemy is ticket 02; application structured logging is ticket 07. Approved subsystem folders are created as implementation arrives rather than empty placeholders.

Runtime identity: Windows, CPython 3.10.11, uv 0.12.23. Locked key versions: FastAPI 0.142.4, Starlette 1.7.0, Pydantic 2.13.5, pydantic-settings 2.15.0, SQLAlchemy 2.0.54, Uvicorn 0.54.0, httpx2 2.13.1, pytest 9.1.1, mypy 1.20.2, Ruff 0.16.10, Hatchling 1.32.4. Consulted primary FastAPI settings/testing, Pydantic errors, SQLAlchemy URL, uv locking docs, and installed Starlette metadata. Links and exact fresh setup commands are in README.

Tests used Nathan-confirmed seams: public Settings/load_settings, and create_app through TestClient. Recorded failing tests before minimal settings loader, distinct database validation, and factory implementation; added configuration edge checks afterward. No PostgreSQL or real data was accessed.

Exact executed verification commands (from `backend/`, with bootstrap uv at `../.venv/Scripts/uv.exe`):

- `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py` — 17 passed.
- `.venv/Scripts/python.exe -m pytest tests/unit/test_app.py` — 1 passed.
- `.venv/Scripts/python.exe -m pytest` — 18 passed in 0.95 seconds.
- `.venv/Scripts/python.exe -m mypy` — success, 8 source files.
- `.venv/Scripts/python.exe -m ruff check .` — all checks passed.
- `.venv/Scripts/python.exe -m ruff format --check .` — 8 files formatted.
- `../.venv/Scripts/uv.exe sync --locked --offline --cache-dir ../.uv-cache` — passed; final lock includes build tools.
- `../.venv/Scripts/uv.exe build --no-build-isolation --offline --cache-dir ../.uv-cache` — built `dist/adflow_backend-0.1.0.tar.gz` and `dist/adflow_backend-0.1.0-py3-none-any.whl`.
- `.venv/Scripts/python.exe -c "from app.main import create_app; print('import valid')"` — passed without environment settings.
- Explicit `load_settings(env_file=Path('../.env.example'))` and `create_app(...)` — passed, title AdFlow.
- Started `.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory --env-file ../.env.example --host 127.0.0.1 --port 18081` in a hidden subprocess; requested `/openapi.json` via urllib, asserted HTTP 200, then terminated/waited for the subprocess — passed.
- `git diff --check` — passed.

Limitations: downloads, Windows TestClient event-loop execution, and build path canonicalization required reviewed execution outside the sandbox. Sandboxed TestClient hung; the identical test passed outside. Only CPython 3.10.11/Windows was exercised. No PostgreSQL integration or Docker result is claimed. Build artifacts and virtual environments are ignored. Existing planning documents remain outside this implementation commit.

Review: parallel Standards and Spec reviews against initial commit `36923fdbbe457df95d6f6afaa983244ab9bc4dd3`. Standards found no violations or material smells. Spec found an unlocked build-backend resolution; corrected by locking Hatchling and building with `--no-build-isolation`, then verified the build again. Complexity: configuration work is bounded by a fixed number of fields; factory creation has no database scans or connection waits.
