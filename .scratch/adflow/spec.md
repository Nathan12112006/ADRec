# AdFlow — Implementation handoff

Status: ready-for-agent

The full-project planning map is complete. This handoff is ready for staged implementation; application code, runtime tests, model results, and benchmarks are not yet complete.

## Authority and entry point

Use the resolved answers in the [AdFlow full-project decision map](map.md) as the canonical contracts. The [original project brief](brief.md) provides intent and preferred stack; accepted decisions override conflicting broader examples or scope. Use [AdFlow domain language](../../CONTEXT.md) when naming concepts.

Start with [What is the smallest reliable Phase 1 backend?](issues/02-phase-one-boundary.md#answer) and its prerequisite [What constitutes a served ad and a valid attributed click?](issues/01-serving-and-events.md#answer). Implement Phase 1 only, verify its completion gate, and report actual files/changes, checks, exact run/test commands, limitations, and the next step before advancing to Phase 2.

## Route and definition of done

The [implementation backlog](../adflow-implementation/spec.md) decomposes all nine phases into 64 local execution tickets with dependencies, acceptance criteria, technical gates and human learning checkpoints. Start with [01 — Create the backend package and configuration foundation](../adflow-implementation/issues/01-backend-foundation.md). These execution IDs are separate from the eleven resolved decision IDs in this directory. No implementation work is marked complete by creating the backlog.

[What staged delivery plan proves completion and interview readiness?](issues/11-delivery-and-learning.md#answer) owns phase order, preparation/startup, scope cuts, retention, reviewer evidence, and learning checkpoints. Keep decision details in their owning tickets rather than copying a second specification into this handoff.

## Decision references

- [What constitutes a served ad and a valid attributed click?](issues/01-serving-and-events.md#answer)
- [What is the smallest reliable Phase 1 backend?](issues/02-phase-one-boundary.md#answer)
- [How will synthetic data and simulated traffic provide honest evidence?](issues/03-synthetic-world.md#answer)
- [What retrieval contract makes FAISS useful and measurable?](issues/04-candidate-retrieval.md#answer)
- [What CTR model and evaluation contract are credible for synthetic data?](issues/05-ctr-evaluation.md#answer)
- [How will two ranking strategies choose winners without redundant scoring?](issues/06-ranking-economics.md#answer)
- [What experiment contract makes comparisons interpretable?](issues/07-experiment-contract.md#answer)
- [What should Redis cache and how will dependency failures behave?](issues/08-cache-and-failures.md#answer)
- [What is the smallest dashboard that demonstrates the complete system?](issues/09-dashboard-demo.md#answer)
- [What measurements will substantiate the performance claims?](issues/10-performance-evidence.md#answer)
- [What staged delivery plan proves completion and interview readiness?](issues/11-delivery-and-learning.md#answer)

## Research pointers

Supporting research is not evidence of successful installation or measured performance. Recheck version-sensitive facts against primary sources when selecting implementation dependencies.

- [FAISS options](research/faiss-options.md)
- [CTR model options](research/ctr-model-options.md)
- [Redis cache options](research/redis-cache-options.md)
- [Load-test options](research/load-test-options.md)

## Comments

Prepared after Nathan confirmed all delivery choices on 2026-10-07. No open wayfinding tickets remain. Public hosting is outside this release.
