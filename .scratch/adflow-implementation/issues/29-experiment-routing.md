# 29 — Route recommendations with immutable experiment attribution

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 25, 26, 27, 28

## Scope

Choose assigned strategy under a consistent start/stop/selection boundary and persist experiment/variant/executed versions with outcomes. Use configured default outside a running experiment; preserve attribution on replay and events after stopping.

## Dependencies

- [25 — Persist coherent ranked selections and explicit response context](25-ranked-selection-context.md)
- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)
- [27 — Persist experiments and stable synthetic-user assignment](27-experiment-schema-assignment.md)
- [28 — Expose validated experiment create/start/stop/list APIs](28-experiment-management.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)
- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Racing starts/stops cannot save ambiguous treatment; later events retain the original variant/cohort.
- [x] Treatment model loss yields 503, never baseline substitution; empty/no-ad behavior remains correct.
- [x] No client-provided variant can rewrite attribution; retrieval configuration is shared.

## Comments

Added migration `0005` to persist experiment ID and assigned variant on recommendations and request outcomes, including no-ad outcomes. New selections take a shared PostgreSQL advisory transaction lock before reading the active experiment and retain it through commit. Experiment start/stop take the matching exclusive transaction lock. This orders lifecycle transitions with newly committed selections; idempotency replay remains before routing and reads saved attribution. The single running experiment's assignment selects control/treatment strategy, model compatibility is rechecked on every new opportunity, and experiment candidate/search/retrieval settings apply to both variants. Missing/incompatible model returns 503 without saving a request outcome or substituting the default strategy. Exact retrieval is an explicit current-catalog scan; unavailable configured HNSW uses exact fallback. Events continue to reference only the recommendation, whose attribution is immutable.

The experiment attribution UUIDs intentionally have no foreign key: experiment deletion is rejected by the existing history trigger, and this preserves PostgreSQL's ability to run the experiment history protection trigger on direct TRUNCATE attempts. App writes always read an existing running experiment under the routing lock. A partial cohort index supports later result queries.

Verification used fresh isolated database `adflow_ticket29d_test` on local PostgreSQL 18.6; other databases were not reset. From `backend/`, with `ADFLOW_RUN_POSTGRES_TESTS=1`, `ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow`, and `ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@127.0.0.1:5432/adflow_ticket29d_test`:

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_ranked_recommendations.py tests/integration/test_http_lifecycle.py tests/integration/test_experiments.py -q
.venv/Scripts/python.exe -m mypy app/services/recommendations.py app/models/records.py app/retrieval/current.py app/retrieval/contracts.py app/experiments/management.py app/api/routes.py app/schemas/lifecycle.py migrations/versions/0005_experiment_attribution.py tests/integration/test_ranked_recommendations.py
.venv/Scripts/python.exe -m ruff check app/services/recommendations.py app/models/records.py app/retrieval/current.py app/retrieval/contracts.py app/experiments/management.py app/api/routes.py app/schemas/lifecycle.py migrations/versions/0005_experiment_attribution.py tests/integration/test_ranked_recommendations.py
.venv/Scripts/python.exe -m ruff format --check app/services/recommendations.py app/models/records.py app/retrieval/current.py app/retrieval/contracts.py app/experiments/management.py app/api/routes.py app/schemas/lifecycle.py migrations/versions/0005_experiment_attribution.py tests/integration/test_ranked_recommendations.py
.venv/Scripts/python.exe -m alembic -x database=test check
```

Results: 66 focused integration tests passed; mypy, Ruff lint/format and Alembic parity passed (`No new upgrade operations detected`). New tests verify active assignment and executed strategy, forbidden client variant input, model loss with no baseline substitution or saved outcome, no-ad assignment replay after stop, impression/click after stop, and a stop racing CTR inference waiting until the in-flight recommendation commits with its original attribution. README updated. PostgreSQL was stopped after checks; databases and history remain retained.
