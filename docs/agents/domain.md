# Domain docs

## Before exploring

Read root `CONTEXT.md` and ADRs under `docs/adr/` that touch the area being explored.

If a root `CONTEXT-MAP.md` exists later, follow its pointers to relevant context documents.

If these files are absent, proceed silently. The domain-modeling skill creates them when terms or decisions are resolved.

## Layout

This project uses a single context: root `CONTEXT.md` for domain terminology and `docs/adr/` for architecture decisions.

## Vocabulary

When naming domain concepts in issues, proposals, hypotheses, or tests, use the terms defined in `CONTEXT.md`.

If a needed concept is missing, reconsider whether it belongs to the project's vocabulary or note the gap for domain-modeling.

## ADR conflicts

When a proposal contradicts an existing ADR, identify the ADR and explain why its decision should be reconsidered.
