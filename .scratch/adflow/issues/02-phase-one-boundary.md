# What is the smallest reliable Phase 1 backend?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 01

## Question

Choose the initial folder structure, module boundaries, schema and migration approach, configuration, health/readiness behavior, and minimum recommendation algorithm. Specify Phase 1 endpoints, database failure semantics, seed sizes, integration-test environment, and the evidence that permits Phase 2 to begin. Keep later retrieval, model, caching, and experiment contracts extensible without implementing them early.

## Comments

The round notes below are chronological discussion history. The final decision is recorded under Answer.

### Confirmed Phase 1 scope and architecture

- Nathan accepted the complete agreed lifecycle: recommendation creation, idempotent request replay, client-confirmed impressions, attributed clicks, and simulated revenue, plus health endpoints and synthetic seed data.
- Experiments, Redis, FAISS, ML, and frontend implementation are deferred beyond Phase 1.
- Nathan accepted one modular backend with thin routes and separate database access, recommendation logic, and event handling, initially using synchronous database access.
- Nathan accepted PostgreSQL through Docker Compose, SQLAlchemy, Alembic migrations, integration tests against a separate PostgreSQL test database, and running FastAPI locally or in Docker.
- Nathan accepted an initial scan of eligible ads: greatest interest overlap wins, then higher bid, then ad ID. Only active ads from active advertisers qualify; with no overlap, bid breaks the tie.
- Storage details, exact folder structure, seed defaults, health/readiness behavior, and completion checks remain open.

Claimed at Nathan's request on 2026-10-07. Its prerequisite, “What constitutes a served ad and a valid attributed click?”, is resolved. Decision discussion has not yet begun.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted the proposed folder structure, separate durable records with uniqueness constraints, decimal money and UTC timestamps, small configurable seed defaults, separate liveness/readiness endpoints, environment configuration, and all Phase 1 completion checks.

## Answer

Resolved with Nathan on 2026-10-07. This is a Phase 1 implementation contract, not evidence that the backend has been built or tested.

### Scope and boundaries

Build one modular FastAPI application with Pydantic request/response validation, synchronous SQLAlchemy database access, PostgreSQL, and Alembic migrations. Routes validate and translate HTTP requests; services own recommendation/event workflows and transaction boundaries; database code owns connection/session concerns; ranking owns the initial selection rule.

Implement the complete lifecycle from [What constitutes a served ad and a valid attributed click?](01-serving-and-events.md#answer). That ticket remains the canonical source for replay, attribution, expiration, event ordering, and accounting semantics.

Include health endpoints, structured errors/logging, configuration, reproducible seeding, tests, Docker support, and setup instructions. Do not implement FAISS, ML, experiments, Redis, frontend, or conversions in Phase 1. Add their modules when their phases begin; avoid empty framework abstractions or placeholder implementations.

### Initial folder structure

```text
backend/
  app/
    api/           # Routes and request dependencies
    core/          # Configuration, errors, logging
    db/            # Connections and transaction handling
    models/        # SQLAlchemy tables
    schemas/       # Pydantic requests and responses
    services/      # Recommendation and event workflows
    ranking/       # Initial selection rule
    main.py
  migrations/      # Versioned Alembic migrations
  scripts/         # Seed generation and development utilities
  tests/
    unit/
    integration/
  pyproject.toml
  Dockerfile
docker-compose.yml
.env.example
README.md
```

Keep existing domain and agent instructions. Package initialization files and migration configuration accompany these directories as needed. Do not create this application structure during the planning session.

### Storage and transaction requirements

- Separate durable records for users, advertisers, ads, request outcomes, recommendations, and events. A request outcome can represent either a selected recommendation or no eligible ad; no-ad outcomes do not create recommendations.
- Use database uniqueness for request keys and recommendation/event-type pairs, plus referential integrity for associated records. Concurrent requests must not create multiple outcomes for one key or duplicate accepted events.
- Retain selected ad details, bid, and attribution sufficient to replay the original selection independently of subsequent ad edits. Keep experiment attribution absent until experiments are introduced; do not create the experimentation subsystem now.
- Use decimal money values and UTC timestamps. Do not represent monetary accounting with binary floating-point values.
- Save recommendation/request outcome atomically; save accepted events and their accounting effects atomically. Transaction handling must recover safely from uniqueness conflicts and roll back failed work.
- Keep records in Phase 1. Expired keys must remain distinguishable from new keys; no automatic pruning or key recycling. Future retention decisions must preserve the lifecycle guarantees.
- Alembic owns schema changes, including initial setup. Document explicit migration commands instead of relying on application startup to silently create tables.

### First selector

Scan ads whose own active flag and advertiser active flag are both true. Maximize the count of distinct shared interests, then higher bid, then ad ID for deterministic ties. Use ascending ad ID as the final deterministic convention. Empty user interests or no overlaps reduce the decision to bid and ID. Zero bids remain eligible; no eligible ads follows the lifecycle ticket's no-ad contract.

The selector is a deliberately simple baseline, not a CTR model. Do not invent predicted probabilities. The recommendation response includes its durable identity and selected ad; omit unsupported ML fields or make them explicitly null in the response schema.

For N eligible ads, U user interests, and A interests per ad, a hash-set overlap implementation has expected O(U + N*A) selection work. It needs O(U + A) working space when iterating ads; materializing all candidates adds space proportional to their count and payload size. Database reads and per-request scans are expected bottlenecks. Phase 2 replaces the broad scan with retrieval; no latency or improvement claim is established here.

### Endpoints, configuration, and failure behavior

- POST /api/v1/recommendations, POST /api/v1/events/impression, and POST /api/v1/events/click follow the lifecycle ticket exactly.
- GET /health/live returns 200 while the application is running, independent of database availability. GET /health/ready checks database connectivity and returns 200 when reachable, otherwise 503. Migration correctness is separately verified by setup and integration checks.
- Use environment-based configuration, with separate application and integration-test database URLs, log level, and database connection timeout settings documented in .env.example. Document both local FastAPI plus Docker PostgreSQL and backend-plus-PostgreSQL Compose operation.
- Validate required keys, positive user identifiers, and recommendation identifier format; malformed requests return 422. Domain failures retain the agreed 404/409/410/503 semantics. Return consistent structured error details and no stack traces.
- Log request identity and relevant recommendation/selection context without exposing credentials. Durable database failure is not a successful ad/event response; bound connection waits so failures do not hang indefinitely.
- Exact compatible dependency versions and runtime configuration are implementation-time verification work; consult primary documentation when selecting them.

### Seed defaults

Default to 100 users, 20 advertisers, and 1,000 ads with configurable counts and a fixed random seed. Generate valid relationships and useful interests for baseline selection. Start with no historical events; demonstrate event creation through the APIs.

This is a development seed, not the full training/benchmark dataset. The existing synthetic-world ticket defines larger datasets, training labels, and simulated traffic. Keep seed/setup commands explicit and document behavior on an already seeded database; do not silently overwrite lifecycle history.

### Completion gate before Phase 2

1. Set up a fresh PostgreSQL database using migrations and generate the default dataset reproducibly.
2. Run the documented recommendation -> impression -> click walkthrough, including an idempotent replay, and inspect that duplicate delivery does not increase counts or revenue.
3. Pass unit tests for deterministic selection, inactive ads/advertisers, zero bids, and empty interests.
4. Pass integration tests against a separate PostgreSQL test database for concurrent request/event retries, response-loss replay, no-ad replay, key/user mismatch, click-before-impression recovery, expiration boundaries, changed bid/inactive ad after selection, unknown identities, malformed inputs, and required database failure behavior.
5. Verify liveness/readiness behavior and backend startup both locally and through Docker. Test setup must target the isolated test database rather than clearing development data.
6. Supply exact setup, migration, seed, run, and test commands, plus a short explanation of transaction safety, selection time/space costs, limitations, and how retrieval will address the scan.

Record actual check results when implementing; planning does not count as passing tests. No numerical performance promise is a Phase 1 requirement.

### Map consequences

The synthetic-world and candidate-retrieval decisions are now available. No new decision ticket is needed: detailed synthetic behavior, retrieval, cache/failure expansion, benchmarks, and delivery/retention concerns already have owners in the map. Application implementation remains outside this planning effort.
