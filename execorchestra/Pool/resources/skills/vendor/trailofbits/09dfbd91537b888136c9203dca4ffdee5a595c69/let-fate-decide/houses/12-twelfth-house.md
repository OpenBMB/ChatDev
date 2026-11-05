# Twelfth House

**Domain**: Blind spots, hidden costs, endings, and unconscious assumptions

## Core Meaning
The Twelfth House describes what is hard to see directly. It points to hidden
state, deferred cleanup, unresolved risk, unclear ownership, stale assumptions,
and endings that need to be handled deliberately.

## Building New Projects
Use this house to identify what should be left out, retired, documented as a
risk, or postponed consciously. It warns against invisible complexity and
features that quietly become obligations.

## Vulnerability Discovery
Use this house to inspect forgotten paths: debug modes, test fixtures,
backdoors, stale credentials, abandoned endpoints, implicit fallbacks, and
assumptions no one has revalidated.

Contrast with the Fourth House: the Fourth House asks what foundational context
must be understood; the Twelfth House asks what hidden or obsolete context is
quietly creating risk.

## Correctness Verification
Use this house to test teardown, cancellation, cleanup, error paths,
unreachable states, timeouts, and any case that is easy to exclude from the
happy-path model.

## Technical Workflow Lenses
- Audit pipeline: look for forgotten endpoints, debug paths, stale credentials,
  dead code, false assumptions, hidden scope, and discarded findings.
- Evidence mode: use negative tests, cleanup checks, unreachable-state review,
  log review, secret scans, and false-positive validation.
- Human context: document deferred risk, cleanup ownership, escalation needs,
  and what should intentionally end.

## Technical Prompt
What is hidden, unfinished, or quietly assumed, and what needs to end cleanly?
