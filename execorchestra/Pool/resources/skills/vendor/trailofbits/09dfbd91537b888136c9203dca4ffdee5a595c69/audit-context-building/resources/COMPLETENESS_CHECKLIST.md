# Completeness Checklist

Before concluding micro-analysis of a function, verify:

---

## Structural Completeness
- [ ] Purpose section: 2+ sentences explaining function role
- [ ] Inputs & Assumptions section: All parameters + implicit inputs documented
- [ ] Outputs & Effects section: All returns, state writes, external calls, events
- [ ] Block-by-Block Analysis: Every logical block analyzed (no gaps)
- [ ] Cross-Function Dependencies: All calls and shared state documented

---

## Content Depth
- [ ] Identified at least 3 invariants (what must always hold)
- [ ] Documented at least 5 assumptions (what is assumed true)
- [ ] Applied First Principles at least once
- [ ] Applied 5 Whys or 5 Hows at least 3 times total
- [ ] Risk analysis for all external interactions (reentrancy, malicious contracts, etc.)

---

## Continuity & Integration
- [ ] Cross-reference with related functions (if internal calls exist, analyze callees)
- [ ] Propagated assumptions from callers (if this function is called by others)
- [ ] Identified invariant couplings (how this function's invariants relate to global system)
- [ ] Tracked data flow across function boundaries (if applicable)

---

## Anti-Hallucination Verification
- [ ] All claims reference specific line numbers (L45, L98-102, etc.)
- [ ] No vague statements ("probably", "might", "seems to") - replaced with "unclear; need to check X"
- [ ] Contradictions resolved (if earlier analysis conflicts with current findings, explicitly updated)
- [ ] Evidence-based: Every invariant/assumption tied to actual code

---

## Completeness Signal

Analysis is complete when:
1. All checklist items above are satisfied
2. No remaining "TODO: analyze X" or "unclear Y" items
3. Full call chain analyzed (for internal calls, jumped into and analyzed)
4. All identified risks have mitigation analysis or acknowledged as unresolved
