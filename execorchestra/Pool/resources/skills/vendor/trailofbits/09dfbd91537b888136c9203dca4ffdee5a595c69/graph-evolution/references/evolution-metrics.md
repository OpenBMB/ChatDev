# Evolution Metrics Reference

This document explains each structural metric the graph-evolution skill
tracks and why it matters for security analysis.

## Contents

- Node changes (added, removed, modified)
- Edge changes (added, removed)
- Complexity evolution
- Attack surface changes
- Blast radius shifts
- Taint propagation changes
- Privilege boundary changes

---

## Node Changes

### Added Nodes

New functions, methods, classes, or modules introduced between snapshots.

**Security relevance:**
- New code has no review history and may lack test coverage
- New public functions expand the attack surface
- New classes may introduce state management complexity

**Triage:** Cross-reference added nodes against the `after` graph's
`entrypoints` subgraph. Added nodes that are entrypoint-reachable get
highest review priority.

### Removed Nodes

Functions, methods, or classes deleted between snapshots.

**Security relevance:**
- Removed validation functions may indicate weakened security controls
- Removed error handlers can expose unhandled edge cases
- Dead code removal is generally positive (reduces attack surface)

**Triage:** Check if removed nodes had `privilege_boundary` or
`taint_propagation` annotations. If so, verify the security function
was replaced, not just deleted.

### Modified Nodes

Nodes present in both snapshots whose properties changed. Tracked
properties:

| Property | What Changed | Security Concern |
|----------|-------------|-----------------|
| `cyclomatic_complexity` | Control flow complexity | Higher CC = more paths to test |
| `parameters` | Function signature | New params may accept untrusted input |
| `return_type` | Return type annotation | Type changes can break callers |
| `line_span` | Lines of code | Significant growth may indicate added logic |

---

## Edge Changes

### Added Edges

New call relationships between functions.

**Security relevance:**
- New calls from untrusted entrypoints to sensitive functions create
  attack paths that did not previously exist
- New `inherits` or `implements` edges can change polymorphic dispatch
- Cross-module calls may violate existing trust boundaries

**Triage:** For each added `calls` edge, check if `source` is in the
`tainted` subgraph and `target` handles sensitive operations.

### Removed Edges

Call relationships that no longer exist.

**Security relevance:**
- Removed validation calls may mean input is no longer checked
- Removed authorization calls can create privilege escalation
- Usually benign during refactoring, but verify removed edges
  between security-relevant nodes

---

## Complexity Evolution

Tracks per-node cyclomatic complexity changes between snapshots.

**Thresholds:**

| CC Delta | Significance |
|----------|-------------|
| +1 to +3 | Minor — likely a new branch or error check |
| +4 to +9 | Moderate — new logic paths need test coverage |
| +10 or more | Major — function is becoming difficult to reason about |
| Negative | Positive — simplification usually reduces bug surface |

**Aggregate signals:**
- Mean CC increase across all modified nodes indicates codebase is
  growing more complex
- Functions that crossed the CC > 10 threshold are new fuzzing
  candidates (per the genotoxic skill's criteria)

---

## Attack Surface Changes

Derived from the `entrypoints` subgraph.

**New entrypoints:** Nodes that appear in the `after` entrypoints but
not `before`. Each new entrypoint is a new way external input reaches
the system.

**Removed entrypoints:** Nodes that were entrypoints in `before` but
not `after`. Usually positive (reduced surface), but verify the
functionality wasn't just moved.

**Trust level changes:** Compare entrypoint trust levels between
snapshots. A function changing from `trusted_internal` to
`untrusted_external` is a significant security event.

---

## Blast Radius Shifts

Derived from the `high_blast_radius` subgraph (nodes with 10+
downstream dependents).

**New high-blast nodes:** Nodes that entered `high_blast_radius` in
`after`. These now affect many downstream functions — bugs here have
wide impact.

**Reduced blast radius:** Nodes that left `high_blast_radius`. Usually
positive (decoupling), but verify the downstream functions weren't
orphaned.

---

## Taint Propagation Changes

Derived from the `tainted` subgraph (nodes reachable from untrusted
entrypoints).

**Newly tainted:** Nodes that entered `tainted` in `after`. These can
now be reached by untrusted input and must validate their inputs.

**De-tainted:** Nodes that left `tainted`. Usually means a trust
boundary was added or an entrypoint was removed.

**Critical combination:** Nodes that are both newly tainted AND had
their CC increase. These are the highest-priority review targets.

---

## Privilege Boundary Changes

Derived from the `privilege_boundary` subgraph (edges where trust
levels change).

**New boundary crossings:** Functions that appeared on a privilege
boundary. These are points where trust transitions happen — common
vulnerability locations.

**Removed boundaries:** Privilege boundaries that disappeared. Could
mean trust was flattened (potentially unsafe) or that the boundary
moved (needs verification).
