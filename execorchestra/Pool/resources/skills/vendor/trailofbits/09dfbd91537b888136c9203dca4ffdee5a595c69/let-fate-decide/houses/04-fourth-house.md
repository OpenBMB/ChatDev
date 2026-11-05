# Fourth House

**Domain**: Foundations, history, context, and hidden dependencies

## Core Meaning
The Fourth House describes what the work rests on. It points to inherited
architecture, assumptions, persistence layers, deployment context, and the
history that shaped the current state.

## Building New Projects
Use this house to decide the base architecture, storage model, configuration
strategy, and migration path. It warns against building attractive surfaces on
unstable ground.

## Vulnerability Discovery
Use this house to inspect implicit trust, legacy behavior, configuration
defaults, environment assumptions, deployment topology, and persistent state
that outlives a single request.

Contrast with the Twelfth House: the Fourth House covers foundations that still
shape the system; the Twelfth House covers forgotten paths and assumptions that
should be retired or revalidated.

## Correctness Verification
Use this house to verify initialization, recovery, migrations, persistence,
default values, and assumptions inherited from previous states.

## Technical Workflow Lenses
- Audit pipeline: build architectural context before hunting; map persistence,
  deployment topology, privileged foundations, and legacy behavior.
- Evidence mode: use initialization tests, migration checks, config review,
  code graph summaries, or environment reproductions.
- Domain lens: for operations and supply chain work, include devcontainers,
  CI defaults, deployment paths, and dependency roots.

## Technical Prompt
What foundation is this work standing on, and what assumption has become
invisible because it has always been there?
