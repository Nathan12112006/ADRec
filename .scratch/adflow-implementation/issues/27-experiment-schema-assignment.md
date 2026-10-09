# 27 — Persist experiments and stable synthetic-user assignment

Status: ready-for-agent
State: done
Type: task
Kind: implementation
Phase: 5 — Experiments
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: Codex
Blocked by: 26

## Scope

Add versioned experiment schema/migrations, stored salt/digest mapping, default 50/50 allocation and pinned ranking/model/feature/retrieval configuration. Enforce one running experiment in PostgreSQL; keep assignments stable across requests/restarts.

## Dependencies

- [26 — Verify and record the ranking phase gate](26-ranking-gate.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Experiment contract](../../adflow/issues/07-experiment-contract.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [x] Known assignments and split boundaries reproduce across processes; user count is not forced exactly 50/50.
- [x] Schema preserves historical experiments and immutable treatment identity.
- [x] Migration/constraint tests include concurrent running-experiment conflicts.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.

Implementation started on 2026-10-08 from `685016027831dfae964f1bc33db021a8eb3037d5` after dependency26 was done. Nathan confirmed public assignment and PostgreSQL schema/migration seams, including cross-process vectors/boundaries, persisted identity/configuration, immutable started treatment/history and concurrent running conflicts, before new tests.

- Added `app.experiments.assignment.AssignmentConfig` and public `assign_variant`. `sha256-bucket-v1` hashes a canonical no-whitespace UTF-8 JSON array of version, lowercase hyphenated experiment UUID, stored 64-hex salt and decimal user ID. The entire unsigned big-endian digest maps to `floor(digest*10000/2^256)`; buckets below `control_basis_points` are control. Default5000, valid0..10000 inclusive; strict positive signed-64-bit user IDs and version/salt/allocation validation. Assignment is constant work for bounded inputs, independent of process hashes, names, request identity and order; finite populations are not forced exactly50/50. New experiment identity can reassign a user.
- Added typed `Experiment` record and history-preserving migration0004: schema/assignment versions, cryptographically generated persisted salt, allocation, both strategy names/versions, pinned model ID/version, feature version, shared retrieval mode/candidate/search/HNSW bounds and vector/vocabulary versions, plus lifecycle timestamps. Defaults are V1 control/V2 treatment, exact retrieval, limit500/search4000. A partial unique index on running status enforces at most one running experiment globally. PostgreSQL identity/lifecycle/history triggers prevent draft identity edits, changes after start (including combined stop/config edits), resume, deletion and truncation. Draft configuration remains editable; stopped records remain immutable and retained. Migration downgrade intentionally preserves history rather than dropping it.
- TDD observed missing public assignment module and missing Experiment record before implementation. Known SHA-256 vectors and exact8307/8308 allocation boundary are checked as literal expectations; fresh subprocesses with different Python hash seeds reproduce them. PostgreSQL tests verify defaults and stored identity, raw invalid configuration, frozen assignment fields/started treatment, HNSW draft edits, stopped history and no resume/delete/truncate. Simultaneous start transactions produce exactly one winner and a `one_running_ranking_experiment` unique conflict; stopping permits a later experiment without deleting history. Strict validator type annotation and SQL formatting were corrected during implementation. No internal mocks or new HTTP endpoints were introduced.
- Focused assignment/schema/history regression: **86 passed in 2.79s**. Final full PostgreSQL-enabled regression: **643 passed in 118.83s**, isolated `adflow_ticket27_test`. Strict mypy **99 source files clean**; whole-backend Ruff lint/format pass; Alembic **no new upgrade operations**; wheel/sdist build and offline lock validation (**65 packages**) pass. [Exact commands](../evidence/ticket27/commands.md) document preparation/configuration and check scope. README explains canonical digest/bucket arithmetic and known vector, units/allocation, schema protection, migration commands, complexity and deferred management/routing.
- [Native smoke](../evidence/ticket27/native-smoke.json) and [Docker smoke](../evidence/ticket27/docker-smoke.json), reproduced by [schema-smoke.py](../evidence/ticket27/schema-smoke.py), migrate a fresh isolated `adflow_ticket27_smoke` to0003, insert durable dataset history, upgrade to0004 and verify old history unchanged. Both load stored assignment configuration in a new process and reproduce variants, reject second running status (`23505`) and treatment/history rewrites (`23514`), retain stopped history and match ORM metadata. Native/Docker CPython **3.10.11/3.12.15**. Docker image `sha256:96165ad9b7f67390d0e4b959981fd1e58f859e2dc76939322be688e80481d4f5`; Compose config/build and evidence lint/format pass. Random experiment IDs/salts differ across smokes; each reproduces its own persisted identity, not a claimed cross-runtime identity equality. Model ID is a valid-format fixture, not a model-availability claim. First Docker setup tried database creation before PostgreSQL finished startup; readiness was then checked before creation and the full smoke passed. No production fix was needed.
- Ticket27 supplies persistence and assignment only. Compatible-model activation/management APIs belong to ticket28; consistent start/stop/selection routing and immutable recommendation attribution belong to ticket29. Schema-level transitions protect stored identity without claiming those APIs/routing or observed experiment effectiveness are complete. Existing recommendation behavior is unchanged. No human learning checkpoint is certified.

### Standards

Independent read-only review against task-start `685016027831dfae964f1bc33db021a8eb3037d5`, including untracked implementation/tests/evidence: **0 documented violations, 0 heuristic findings**. Domain vocabulary, tracker execution, canonical assignment, schema/migration protections and evidence scope pass. Migration/ORM constraint duplication preserves the historical migration definition. No tests were rerun by the reviewer.

### Spec

Independent read-only review: **0 actionable findings**. Persisted assignment algorithm/salt, canonical bucket mapping, default allocation, cross-process vectors, pinned configuration, immutable history/treatment and database concurrent-start exclusion satisfy ticket27. Tests and native/Docker upgrade evidence support the recorded behavior. Management/model activation and routing/attribution remain correctly deferred to tickets28/29.

Review total: Standards 0; Spec 0; no outstanding findings. All acceptance criteria pass; ticket27 is complete and ticket28 is unblocked. Native PostgreSQL and the isolated Docker verification PostgreSQL were stopped cleanly after checks; all databases, Docker data/container/network and original model/history artifacts remain retained. Final whitespace/evidence checks pass. The implement skill's commit is on the current `main` branch.
