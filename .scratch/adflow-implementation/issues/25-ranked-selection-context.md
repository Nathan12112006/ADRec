# 25 — Persist coherent ranked selections and explicit response context

Status: ready-for-agent
State: open
Type: task
Kind: implementation
Phase: 4 — Ranking and selection
Parent: [AdFlow implementation backlog](../spec.md)
Assignee: unassigned
Blocked by: 05, 23, 24

## Scope

Wire strategy selection into the recommendation workflow with eligibility/bid revalidation and coherent immutable selection metadata. Expose score meaning, strategy/retrieval/model/feature versions and null V1 CTR. Model-required nonempty V2 requests fail 503 without substitution.

## Dependencies

- [05 — Persist recommendations and idempotent request outcomes](05-recommendation-workflow.md)
- [23 — Verify and record the CTR-model phase gate](23-ctr-gate.md)
- [24 — Implement interchangeable V1 and V2 ranking strategies](24-ranking-strategies.md)

Dependencies refer to implementation tickets in this directory. Begin only after every dependency has `State: done`. Follow the [shared execution and evidence rules](../spec.md#execution-and-evidence).

## Governing decisions

- [Serving and event lifecycle](../../adflow/issues/01-serving-and-events.md#answer)
- [CTR model and evaluation](../../adflow/issues/05-ctr-evaluation.md#answer)
- [Ranking economics](../../adflow/issues/06-ranking-economics.md#answer)

The resolved answers above are authoritative, including edge cases not repeated here.

## Acceptance criteria

- [ ] Tests reproduce a lower-bid expected-value winner, coherent changed-metadata handling and saved-result replay.
- [ ] Empty candidates follow no-ad without model inference; invalid model/outputs preserve failure semantics.
- [ ] Click credits still use captured bid, never expected-value score or a clearing price.

## Comments

Created on 2026-10-07 from the accepted implementation handoff. No implementation, verification or human exercise is claimed complete.
