# Technical Context Lenses

These lenses apply across a wide range of technical workflows, but they cluster
into a small set of recurring patterns. Use them to translate a house or card
into the kind of work currently being done.

## Audit Pipeline Stage

Use this lens when the task is part of a security review or codebase critique.
Map the spread to the current phase:

- Scoping and setup: what is in scope, what is excluded, and what must be
  understood first.
- Attack-surface mapping: entry points, trust boundaries, privileged paths,
  assets, state transitions, and external dependencies.
- Discovery: creative hypotheses, known bug classes, unusual inputs, and
  paths that ordinary review may miss.
- Validation: source traces, tests, fuzz cases, proofs, exploitability checks,
  and false-positive elimination.
- Reporting and regression: impact, reproduction, remediation, and tests that
  keep the issue from returning.

## Evidence Mode

Use this lens to decide what kind of evidence should follow the reading. A
Tarot spread can prioritize attention, but the next step should produce one of
these evidence types:

- Source-level trace or code graph path.
- Unit, integration, property, fuzz, mutation, or regression test.
- Static-analysis query, SARIF finding, or semgrep/codeql rule.
- Protocol diagram, formal model, invariant, or spec-to-code comparison.
- Exploit proof, crash reproducer, timing measurement, or production telemetry.
- Written rationale, report section, decision log, or stakeholder-ready summary.

## Domain Lens

Use this lens to adapt general language to the actual domain:

- Smart contracts and DeFi: assets, access control, arithmetic precision,
  state machines, hooks, bridges, governance, MEV, and token behavior.
- Crypto and protocols: transcripts, roles, keys, randomness, authentication,
  secrecy, replay, side channels, and formal security properties.
- Appsec, web, and mobile: endpoints, parsers, sessions, OAuth, uploads,
  webhooks, cloud backends, and captured traffic.
- Native, binary, and systems work: memory safety, integer behavior, races,
  debug data, reverse engineering, crashes, and sanitizer results.
- CI/CD, supply chain, and operations: dependencies, workflow permissions,
  agentic actions, deploy paths, production errors, and ownership.
- Product, docs, and stakeholder work: requirements, usability, report quality,
  positioning, scope, status, and handoff clarity.

## Failure Class Lens

Use this lens when the reading needs to become a concrete bug-hunting prompt:

- Access control, confused deputy behavior, authorization bypass, and privilege
  escalation.
- State-machine mistakes, broken lifecycle transitions, races, retries, and
  partial failure.
- Arithmetic, precision, unit, dimensional, bounds, overflow, and accounting
  errors.
- Parser, serialization, protocol, type-safety, and interface mismatches.
- Secrets, information leakage, side channels, logging exposure, and insecure
  defaults.
- Supply-chain compromise, dependency takeover, CI injection, sandbox escape,
  and unsafe automation.
- Missing tests, weak harnesses, unreachable coverage, survived mutants, and
  unverified invariants.

## Human and Organizational Lens

Use this lens when the work depends on people, teams, or decisions rather than
only code:

- Who owns the decision, risk, artifact, or follow-up?
- What needs to be escalated, documented, or turned into a report?
- What context is missing from stakeholders, users, maintainers, or reviewers?
- What would reduce ambiguity for the next person to touch the work?
- What is the team's capacity, confidence, and tolerance for change?

## House Affinity Map

| House | Strongest Corpus Lenses |
|-------|--------------------------|
| 1 - Self | Scoping, entry points, first assumptions, initial attack surface |
| 2 - Resources | Assets, invariants, budgets, ownership, scarcity |
| 3 - Communication | APIs, protocols, parsers, schemas, docs, logs |
| 4 - Foundations | Architecture, persistence, deployment context, legacy assumptions |
| 5 - Creativity | Fuzzing, abuse cases, prototypes, exploratory testing |
| 6 - Practice | CI, harnesses, regression tests, observability, maintenance |
| 7 - Partnership | Integrations, auth contracts, users, vendors, external APIs |
| 8 - Transformation | State transitions, migrations, secrets, escalation, shared authority |
| 9 - Exploration | Specs, standards, formal models, protocol reasoning, research |
| 10 - Calling | Release readiness, impact, reportability, production accountability |
| 11 - Community | Supply chain, ecosystem, shared infrastructure, governance |
| 12 - The Hidden | Forgotten paths, cleanup, stale assumptions, blind spots |
