# Issue tracker: Local Markdown

Issues and specs live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- Specs: `.scratch/<feature-slug>/spec.md`.
- Implementation tickets: `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, with one file per ticket.
- Record triage state in a `Status:` line near the top; use the roles in `triage-labels.md`.
- Append comments and conversation history under `## Comments`.

## Publishing and fetching

When a skill says to publish to the issue tracker, create the appropriate file under `.scratch/<feature-slug>/`, creating directories as needed.

When a skill says to fetch a ticket, read the referenced file. The user will normally supply its path or issue number.

## Wayfinding operations

- Map: `.scratch/<effort>/map.md`, containing Notes, Decisions-so-far, and Fog.
- Child ticket: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with its question in the body.
- Record ticket type with `Type: research`, `prototype`, `grilling`, or `task`.
- Record claimed or completed work with `Status: claimed` or `Status: resolved`.
- Dependencies: `Blocked by: NN, NN`. A ticket is unblocked when all listed tickets are resolved.
- Frontier: scan for open, unblocked, unclaimed tickets; choose the lowest number first.
- Claim: save `Status: claimed` before beginning work.
- Resolve: append the answer under `## Answer`, save `Status: resolved`, then append a gist and link to Decisions-so-far in the map.
