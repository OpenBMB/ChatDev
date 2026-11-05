# Third House

**Domain**: Communication, learning, interfaces, and local connections

## Core Meaning
The Third House describes exchange: names, messages, protocols, documentation,
small decisions, and the local links between parts of a system.

## Building New Projects
Use this house to shape APIs, component boundaries, naming, docs, schemas, and
the early developer experience. It favors clarity over cleverness.

## Vulnerability Discovery
Use this house to inspect parsers, protocol handling, serialization,
deserialization, request routing, logs, CLI arguments, and any place where
meaning crosses a boundary.

## Correctness Verification
Use this house to verify contracts between components. It maps to type
boundaries, message formats, state synchronization, error propagation, and
whether two parts of the system agree on the same facts.

## Technical Workflow Lenses
- Audit pipeline: inspect parsers, schemas, protocol messages, logs, CLI
  arguments, and API contracts where meaning crosses a boundary.
- Evidence mode: use parser fuzzing, schema tests, protocol diagrams, static
  rules, or spec-to-code comparisons.
- Human context: improve names, docs, and report language when ambiguity is the
  thing creating risk.

## Technical Prompt
Where is meaning being translated, and what misunderstanding would cause the
system to fail?
