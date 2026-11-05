# Second House

**Domain**: Resources, values, constraints, and preservation

## Core Meaning
The Second House describes what is available, what is scarce, and what must not
be wasted. It asks which resources, values, or invariants should constrain the
plan.

## Building New Projects
Use this house to reason about budgets: time, complexity, dependencies,
platform limits, team expertise, and which pieces deserve durable foundations.

## Vulnerability Discovery
Use this house to examine assets and incentives. It maps to funds, secrets,
privileges, quotas, availability, and anything an attacker could steal,
degrade, lock, or manipulate.

Contrast with the Eighth House: the Second House treats secrets and privileges
as assets to protect; the Eighth House focuses on how they change hands,
escalate, or become exposed during transitions.

## Correctness Verification
Use this house to protect invariants. It maps to conservation properties,
resource accounting, bounds, ownership, permissions, and state that must remain
consistent across transitions.

## Technical Workflow Lenses
- Audit pipeline: enumerate assets, privileges, quotas, budgets, and incentives
  before ranking risk.
- Evidence mode: prefer accounting tests, invariant checks, permission traces,
  dimensional analysis, or scarcity proofs.
- Domain lens: in DeFi and crypto, treat units, balances, keys, randomness, and
  token behavior as first-class resources.

## Technical Prompt
What resource or invariant gives this task its real value, and what would be
costly to lose?
