# Output Requirements & Quality Thresholds

When performing spec-to-code compliance analysis, Claude MUST produce structured IR following the formats demonstrated in [IR_EXAMPLES.md](IR_EXAMPLES.md).

---

## Required IR Production

For EACH phase, output MUST include:

### Phase 2 - Spec-IR (mandatory)
- MUST extract ALL intended behavior into Spec-IR records
- Each record MUST include: `id`, `spec_excerpt`, `source_section`, `source_document`, `semantic_type`, `normalized_form`, `confidence`
- MUST use YAML format matching Example 1
- MUST extract minimum 10 Spec-IR items for any non-trivial specification (5+ pages of documentation)
- MUST include confidence scores (0-1) for all extractions
- MUST document both explicit and implicit invariants

### Phase 3 - Code-IR (mandatory)
- MUST analyze EVERY function with structured extraction
- Each record MUST include: `id`, `file`, `function`, `lines`, `visibility`, `modifiers`, `behavior` (preconditions, state_reads, state_writes, computations, external_calls, events, postconditions), `invariants_enforced`
- MUST use YAML format matching Example 2
- MUST document line numbers for ALL claims (every precondition, state read/write, computation, external call)
- MUST capture full control flow (all conditional branches, revert paths)
- MUST identify all external interactions with risk analysis

### Phase 4 - Alignment-IR (mandatory)
- MUST compare EVERY Spec-IR item against Code-IR
- Each record MUST include: `id`, `spec_ref`, `code_ref`, `spec_claim`, `code_behavior`, `match_type`, `confidence`, `reasoning`, `evidence`
- MUST classify using exactly one of: `full_match`, `partial_match`, `mismatch`, `missing_in_code`, `code_stronger_than_spec`, `code_weaker_than_spec`
- MUST use YAML format matching Example 3
- MUST provide reasoning trace explaining WHY classification was chosen
- MUST include evidence with exact quotes and locations from both spec and code
- Every Spec-IR item MUST have corresponding Alignment record (no gaps)

### Phase 5 - Divergence Findings (when applicable)
- MUST create detailed finding for EVERY `mismatch`, `missing_in_code`, or `code_weaker_than_spec`
- Each finding MUST include: `id`, `severity`, `title`, `spec_claim`, `code_finding`, `match_type`, `confidence`, `reasoning`, `evidence`, `exploitability`, `remediation`
- MUST use YAML format matching Example 4
- MUST quantify impact with concrete numbers (not "could be exploited" but "attacker gains $X, victim loses $Y")
- MUST provide exploitability analysis with attack scenarios (prerequisites, sequence, impact)
- MUST include remediation with code examples and testing requirements

### Phase 6 - Final Report (mandatory)
- MUST produce structured report following 16-section format defined in Phase 6
- MUST include all IR artifacts (Spec-IR, Code-IR, Alignment-IR, Divergence Findings)
- MUST provide Full Alignment Matrix showing all spec→code mappings
- MUST quantify risk and prioritize remediations

---

## Quality Thresholds

A complete spec-to-code compliance analysis MUST achieve:

### Spec-IR minimum standards:
- Minimum 10 Spec-IR items for non-trivial specifications
- At least 3 invariants extracted (explicit or implicit)
- At least 2 security requirements identified (MUST/NEVER/ALWAYS keywords)
- At least 1 math formula or economic assumption documented
- Confidence scores for all extractions (no missing scores)

### Code-IR minimum standards:
- EVERY public/external function analyzed (no gaps in coverage)
- Minimum 3 invariants documented per analyzed function
- ALL external calls identified with return handling documented
- ALL state modifications tracked (reads and writes)
- Line number citations for ALL claims (100% traceability)

### Alignment-IR minimum standards:
- EVERY Spec-IR item has corresponding Alignment record (complete matrix)
- Reasoning provided for all match_type classifications
- Evidence includes exact quotes from both spec and code
- Ambiguities explicitly flagged (never guessed or inferred)
- Confidence scores reflect actual certainty (not placeholder 1.0 for everything)

### Divergence Finding minimum standards:
- EVERY CRITICAL/HIGH finding has exploit scenario with concrete attack sequence
- Economic impact quantified with dollar amounts or percentages
- Remediation includes code examples (not just "add validation")
- Testing requirements specified (unit tests, integration tests, fuzz tests)
- Breaking changes documented with migration path

---

## Format Consistency

- MUST use YAML for all IR records (Spec-IR, Code-IR, Alignment-IR, Divergence)
- MUST use consistent field names across all records (e.g., `spec_excerpt` not `specification_text`)
- MUST reference line numbers in format: `L45`, `lines: 89-135`, `line 108`
- MUST cite spec locations: `"Section §4.1"`, `"Page 7, paragraph 3"`, `"Whitepaper section 2.3"`
- MUST use markdown code blocks with language tags: ` ```yaml `, ` ```solidity `
- MUST separate major sections with `---` horizontal rules

---

## Anti-Hallucination Requirements

- NEVER infer behavior not present in spec or code
- ALWAYS quote exact text (spec_quote, code_quote in evidence)
- ALWAYS provide line numbers for code claims
- ALWAYS provide section/page for spec claims
- If uncertain: Set confidence < 0.8 and document ambiguity
- If spec is silent: Classify as `UNDOCUMENTED`, never guess
- If code adds behavior: Classify as `code_stronger_than_spec`, document in Alignment-IR
