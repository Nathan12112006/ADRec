# 52 — Verify explicit artifact preparation and fresh Docker startup

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 9 — Final polish
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 51

## Scope

Run the documented fresh-checkout flow: configuration, build, migrations, seed, index build, history generation, training and startup with explicit preparation commands.

## Dependencies

- [51 — Verify and record the performance evidence phase gate](51-performance-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Phase 1 backend boundary](../../adflow/issues/02-phase-one-boundary.md#answer)
- [Synthetic data and traffic](../../adflow/issues/03-synthetic-world.md#answer)
- [Candidate retrieval](../../adflow/issues/04-candidate-retrieval.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Redis and dependency failures](../../adflow/issues/08-cache-and-failures.md#answer)
- [Delivery and learning](../../adflow/issues/11-delivery-and-learning.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Application startup does not silently generate datasets or train models.
- [ ] Document small demo and full evidence dataset choices, prerequisites and artifact locations.
- [ ] Verify health, recommendation/events, experiment start/stop, simulator and dashboard in Docker; record actual commands/results.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

### Isolated Docker walkthrough — 2026-10-09

Kept the existing `adflow` and `adflow_benchmark` databases intact. Created a new
`adflow_demo_walkthrough` database in the running Compose PostgreSQL service, then ran:

```powershell
docker compose config --quiet
docker compose exec -T postgres createdb -U adflow adflow_demo_walkthrough
docker compose run --rm -e ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@postgres:5432/adflow_demo_walkthrough backend python -m alembic upgrade head
docker compose run --rm -e ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@postgres:5432/adflow_demo_walkthrough backend python -m app.seeding.cli --seed 52001 --users 100 --advertisers 20 --ads 1000
docker compose run --rm -e ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@postgres:5432/adflow_demo_walkthrough backend python -m app.retrieval.cli build --dataset-id ff1f2960-9b53-50e3-a0a8-9baa41a6b399 --output /artifacts/walkthrough-flat-v1
docker compose run --rm -e ADFLOW_DATABASE_URL=postgresql+psycopg://adflow:adflow@postgres:5432/adflow_demo_app -e ADFLOW_TEST_DATABASE_URL=postgresql+psycopg://adflow:adflow@postgres:5432/adflow_demo_walkthrough backend python -m app.history.cli --database test --dataset-id ff1f2960-9b53-50e3-a0a8-9baa41a6b399 --output /artifacts/walkthrough-history --impressions 10000 --batch-size 1000 --seed 52
docker compose run --rm backend python -m app.ctr.dataset --history /artifacts/walkthrough-history --output /artifacts/walkthrough-features
docker compose run --rm backend python -m app.ctr.training --features /artifacts/walkthrough-features --output /artifacts/walkthrough-model
docker compose run --rm backend python -m app.ctr.evaluation --features /artifacts/walkthrough-features --model /artifacts/walkthrough-model --output /artifacts/walkthrough-evaluation
docker compose run --rm backend python -m app.ctr.artifacts --model /artifacts/walkthrough-model --evaluation /artifacts/walkthrough-evaluation --output /artifacts/walkthrough-bundle
```

Configuration/build: Compose configuration validated; the digest-pinned backend and
dashboard images were built for the running demo. The entity manifest reports seed
52001, dataset `ff1f2960-9b53-50e3-a0a8-9baa41a6b399`, 100 users, 20 advertisers and
1,000 ads. The Flat snapshot completed with 1,000 vectors. History generation completed
10,000 synthetic exposures and 229 clicks; chronological feature splits contained 7,000 /
1,500 / 1,500 rows. Training, held-out evaluation and bundle packaging all produced
complete manifests. All output directories are under the Compose `index_artifacts`
volume at `/artifacts`; none are produced implicitly by API startup.

Started an isolated one-worker API container named `adflow-walkthrough-api` at
`http://127.0.0.1:18002`, configured with the walkthrough database, Flat snapshot and
validated bundle. `/health/ready` returned `ready`, PostgreSQL `ready`, retrieval `flat`,
V2 capability enabled and the expected model ID. A recommendation, impression and click
succeeded; the click was credited once for the saved bid. Created and started experiment
`walkthrough-smoke`, routed one recommendation to `control`, accepted its impression and
click, then stopped it. A direct query confirmed the experiment persisted as `stopped`
and the recommendation retained its experiment/variant attribution. A 3-second simulator
run completed 3/3 opportunities at the requested 1/s; the isolated database reconciled
four request outcomes, four impressions, three clicks and `$14.9500` in simulated click
credit. The existing Docker dashboard at `http://127.0.0.1:5174` returned `ok`; its
overview, experiment and performance views loaded synthetic data. Ticket 53 retains the
actual screenshots.

Startup behavior is explicit in `backend/app/main.py`: lifespan setup opens the database,
initializes optional cache/model state, loads configured immutable artifacts, and closes
resources. It does not invoke Alembic, the entity seeder, history generator, feature
builder, evaluator or trainer. README now describes the default small demo, separate
100,000-ad retrieval evidence and 1,000,000-exposure synthetic history options, and the
`/artifacts` volume paths. It also states that routine `docker compose up` does not
migrate or prepare data.
