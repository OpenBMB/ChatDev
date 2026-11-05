# Eighth House

**Domain**: Transformation, risk, shared state, secrets, and deep change

## Core Meaning
The Eighth House describes what changes under pressure. It points to risk,
shared ownership, irreversible transitions, secrets, migrations, and places
where failure has second-order effects.

## Building New Projects
Use this house to reason about migrations, data ownership, auth, secret
handling, payment flows, destructive actions, and architectural choices that
will be expensive to reverse.

## Vulnerability Discovery
Use this house to inspect privilege escalation, confused deputy behavior,
secret exposure, shared mutable state, reentrancy, unsafe migrations, and
operations that transform authority or value.

Contrast with the Second House: the Second House asks what assets need
protection; the Eighth House asks what can go wrong when those assets,
permissions, or states are transferred, transformed, or partially updated.

## Correctness Verification
Use this house to verify state transitions, rollback behavior, atomicity,
authorization invariants, data lifecycle rules, and whether partial failure
leaves the system in a dangerous state.

## Technical Workflow Lenses
- Audit pipeline: hunt transition bugs: escalation, reentrancy, races, partial
  updates, migrations, secret movement, and shared authority.
- Evidence mode: use state-machine analysis, concurrency tests, exploit PoCs,
  rollback tests, invariant checks, or transaction traces.
- Domain lens: in smart contracts and protocols, focus on value movement,
  authority changes, replay, lifecycle transitions, and cross-component state.

## Technical Prompt
What changes irreversibly here, and what risk appears only when ownership or
state is shared?
