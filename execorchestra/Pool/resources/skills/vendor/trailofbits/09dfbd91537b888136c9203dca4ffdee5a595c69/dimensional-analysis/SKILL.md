---
name: dimensional-analysis
description: "Annotates codebases with dimensional analysis comments documenting units, dimensions, and decimal scaling. Use when someone asks to annotate units in a codebase, perform a dimensional analysis, or find vulnerabilities in a DeFi protocol, offchain code, or other blockchain-related codebase with arithmetic. Prevents dimensional mismatches and catches formula bugs early."
allowed-tools: Read Write Grep List Glob Task TodoRead TodoWrite
---

# Dimensional Analysis Skill

This skill orchestrates a dimensional-analysis pipeline for codebases that perform numeric computations with mixed units, precisions, or scaling factors. The main skill context is a workflow controller only: it delegates scanning, vocabulary discovery, annotation, propagation, and validation to specialized subagents, then manages batching, persistence, retries, coverage gates, and final reporting.

## When to Use

- Annotating a codebase with unit/dimension comments (e.g., `D18{tok}`, `D27{UoA/tok}`)
- Performing dimensional analysis on DeFi protocols, financial code, or scientific computations
- Hunting for arithmetic bugs caused by unit mismatches, missing scaling, or precision loss
- Auditing codebases with mixed decimal precisions or fixed-point arithmetic

## When NOT to Use

- Codebases with no numeric arithmetic or unit conversions — there is nothing to annotate
- Pure integer counting logic (loop indices, array lengths) with no physical or financial dimensions
- When you only need a quick spot-check of a single formula — read the code directly instead of running the full pipeline

## Execution Mode

This skill runs in one mode only: `full-auto`.
This is a workflow-based skill that delegates step-specific work to specialized agents via the `Task` tool. You orchestrate the overall process, manage coverage and state persistence, and ensure that every in-scope file is processed through each step of the pipeline.

- Always run the full pipeline in this order: Step 1 -> Step 2 -> Step 3 -> Step 4.
- The main skill context must not perform repository-wide dimensional analysis, annotation, propagation, or bug validation itself when a dedicated subagent exists for that step.
- The main skill context may inspect artifacts, manifests, and subagent outputs only as needed to route work, build prompts, persist state, and determine completion.
- Any mode argument provided by the caller is ignored.
- Report all results at the end in a single summary.

When you start a step, report it:

```text
Starting Step: Step {n}
```

## Scope and Coverage Guarantees

This skill must audit **all in-scope arithmetic files**, including large repositories.

- In-scope files are defined by Step 1 scanner output (`files` array), across **all** priority tiers (CRITICAL, HIGH, MEDIUM, LOW).
- If Step 1 narrows inputs for vocabulary discovery (for example, CRITICAL/HIGH only), that narrowing applies to discovery only. It **never** reduces annotation or validation scope.
- `arithmetic-scanner` persists the in-scope file manifest to `DIMENSIONAL_SCOPE.json` in the project root, and that manifest is the source of truth for Steps 2-4.
- A file is considered fully covered only when all three statuses are present:
  - `step2`: anchor annotation completed (or explicit no-anchor result)
  - `step3`: propagation completed (or explicit no-propagation result)
  - `step4`: validation completed
- `dimension-discoverer` persists the discovered dimensional vocabulary to `DIMENSIONAL_UNITS.md` in the project root for reuse by later steps and future runs.
- When a file ends in a terminal `BLOCKED` state, persist the blocking reason and retry count in `DIMENSIONAL_SCOPE.json` and reflect the same file in `coverage.unprocessed_files`.
- Do not finish while any in-scope file remains unprocessed in any step.

## Delegation Contract

- `arithmetic-scanner` owns repository scanning, arithmetic-file prioritization, and writing `DIMENSIONAL_SCOPE.json`.
- `dimension-discoverer` owns dimensional vocabulary discovery, unit inference, and writing `DIMENSIONAL_UNITS.md`.
- `dimension-annotator` owns annotation format decisions, anchor-point edits, and comment-writing behavior.
- `dimension-propagator` owns propagation logic, inferred annotations, and mismatch reporting during tracing.
- `dimension-validator` owns bug detection, red-flag evaluation, rationalization rejection, and confirmation or refutation of propagated mismatches.
- The main skill context must not substitute its own dimensional reasoning for skipped or unlaunched subagents. If a step requires specialized reasoning, launch the corresponding subagent.
- Use reference files as subagent support material. Pass them to the relevant step in prompts instead of treating them as instructions for the main skill context.

## Workflow

Follow these sections in order. Do not advance until the current step satisfies its completion gate.

### Shared Orchestration Rules

- `DIMENSIONAL_SCOPE.json` and `DIMENSIONAL_UNITS.md` live in the project root.
- The main skill context verifies Step 1 artifacts but does not write either Step 1 artifact itself.
- `DIMENSIONAL_SCOPE.json.in_scope_files` is the source of truth for Steps 2-4. Never derive later scope from discovery-only inputs.
- When a later step reaches terminal `BLOCKED`, persist the matching `step*_reason` and `step*_retry_count` fields on the file entry in `DIMENSIONAL_SCOPE.json`.
- `coverage.unprocessed_files` must be derived from terminal `BLOCKED` entries in `DIMENSIONAL_SCOPE.json` using `{ "path": "...", "blocked_step": "step2|step3|step4", "reason": "...", "retry_count": 1 }`.
- A step may retry a `BLOCKED` file once with a focused prompt. If it is still `BLOCKED`, keep the documented reason and continue. Do not finalize while any file remains `PENDING`.

### Step 1: Vocabulary and Scope Discovery

If cached artifacts cannot be reused, delegate repository scanning to `arithmetic-scanner` and vocabulary discovery to `dimension-discoverer`. Do not do that step-specific analysis directly in the main skill context.

1. Check whether `DIMENSIONAL_UNITS.md` and `DIMENSIONAL_SCOPE.json` already exist in the project root.
2. If both exist, read them and confirm:
   - `DIMENSIONAL_SCOPE.json.project_root` matches the current repo root
   - `DIMENSIONAL_SCOPE.json` contains `in_scope_files`, `discoverer_focus_files`, `recommended_discovery_order`, and per-file `step2`, `step3`, `step4` fields
   - `DIMENSIONAL_UNITS.md` is a usable dimensional vocabulary for this repo
3. If either artifact is stale, malformed, missing required structure, or clearly for another repo, discard reuse and rerun the rest of Step 1.
4. If both artifacts are valid, reuse them directly. If `in_scope_files` is empty, skip Steps 2-4 and produce final output with zero findings.
5. Otherwise use the `Task` tool to spawn the `arithmetic-scanner` agent. Its prompt must include:
   - project root path
   - absolute output path for `DIMENSIONAL_SCOPE.json`
   - instruction to write the Step 1 scope manifest to disk and return the same scope data in its report
6. The scanner owns Step 1 scope persistence. It must:
   - identify dimensional-arithmetic files and prioritize them as usual
   - write `DIMENSIONAL_SCOPE.json` with `project_root`, `in_scope_files`, `discoverer_focus_files`, and `recommended_discovery_order`
   - initialize every in-scope file with `step2: "PENDING"`, `step3: "PENDING"`, and `step4: "PENDING"`
   - still write an empty manifest when no arithmetic files are found
   - still narrow `discoverer_focus_files` to CRITICAL/HIGH when more than 50 arithmetic files are found, while keeping all priorities in `in_scope_files`
7. After the scanner completes, read `DIMENSIONAL_SCOPE.json` from disk and confirm it exists and contains the required Step 1 fields before continuing.
8. Use the `Task` tool to spawn the `dimension-discoverer` agent. Its prompt must include:
   - project root path
   - absolute path to `DIMENSIONAL_SCOPE.json`
   - absolute output path for `DIMENSIONAL_UNITS.md`
   - prioritized `discoverer_focus_files` with each file's path, priority, score, and category
   - `recommended_discovery_order`
9. The discoverer owns Step 1 vocabulary persistence. It must read `DIMENSIONAL_SCOPE.json` as the Step 1 source of truth and write `DIMENSIONAL_UNITS.md` with `Base Units`, `Derived Units`, and `Precision Prefixes` sections. If `in_scope_files` is empty, it must still write the same headings with empty sections.
10. Step 1 is complete only when both artifacts exist on disk, pass the reuse checks above, and correctly represent the zero-file case. If `in_scope_files` is empty after the discoverer writes `DIMENSIONAL_UNITS.md`, skip Steps 2-4 and produce final output with zero findings.

### Step 2: Anchor Annotation

The main skill context must not add annotations itself. Use the `Task` tool to spawn `dimension-annotator` agents for all anchor-point annotation work. For full examples and annotation format details, see `[{baseDir}/references/annotate.md]({baseDir}/references/annotate.md)`.

- Read `DIMENSIONAL_SCOPE.json` and build batches from `in_scope_files`. Every in-scope file, including MEDIUM and LOW priority files, must receive a Step 2 outcome.
- Batch files instead of spawning one agent per file:
  - `<= 10` files: one batch
  - `11-30` files: one batch per category
  - `> 30` files: one batch per category, splitting categories larger than 10 files into sub-batches of about 8 files
- Launch categories in Step 1 recommended discovery order: math libraries, then oracles, then core logic, then peripheral. Batches inside the same category may run in parallel.
- Before launching annotators, set `step2 = "PENDING"` for every in-scope file and persist the updated `DIMENSIONAL_SCOPE.json`.
- Each annotator prompt must include:
  - absolute path to `DIMENSIONAL_UNITS.md`
  - absolute path to `DIMENSIONAL_SCOPE.json`
  - assigned file paths in order
  - each file's category and matched patterns from scanner output
  - summary of previously annotated interfaces or types from earlier batches, when applicable
  - required per-file status output: `ANNOTATED`, `REVIEWED_NO_ANCHOR_CHANGES`, or `BLOCKED` plus a one-line justification
- After each batch, immediately persist each assigned file to exactly one Step 2 status:
  - `ANNOTATED`
  - `REVIEWED_NO_ANCHOR_CHANGES`
  - `BLOCKED`
- If a file is `BLOCKED`, also persist `step2_reason` and `step2_retry_count`. Retry each `BLOCKED` file once with a focused prompt.
- Do not continue to Step 3 while any file remains `PENDING` in on-disk manifest state.

### Step 3: Dimension Propagation

The main skill context must not perform propagation reasoning itself. Use the `Task` tool to spawn `dimension-propagator` agents to extend annotations through arithmetic, function calls, and assignments. For algebra details, see `[{baseDir}/references/dimension-algebra.md]({baseDir}/references/dimension-algebra.md)`.

- Read `DIMENSIONAL_SCOPE.json` and build propagation batches from `in_scope_files`. Every in-scope file must receive a Step 3 outcome.
- Use the same batching rules and category ordering as Step 2.
- Before launching propagators, confirm every file already has a non-pending Step 2 status.
- Then set `step3 = "PENDING"` for every in-scope file and persist the updated manifest.
- Each propagator prompt must include:
  - absolute path to `DIMENSIONAL_UNITS.md`
  - absolute path to `DIMENSIONAL_SCOPE.json`
  - assigned file paths in order
  - each file's category and matched patterns
  - summary of Step 2 anchor annotations for the assigned files and any upstream interfaces they depend on
  - required per-file status output: `PROPAGATED`, `REVIEWED_NO_PROPAGATION_CHANGES`, or `BLOCKED` plus a one-line justification
- After each batch, immediately persist each assigned file to exactly one Step 3 status:
  - `PROPAGATED`
  - `REVIEWED_NO_PROPAGATION_CHANGES`
  - `BLOCKED`
- If a file is `BLOCKED`, also persist `step3_reason` and `step3_retry_count`. Retry each `BLOCKED` file once with a focused prompt.
- After all propagators complete, aggregate:
  - annotations added by confidence level (`CERTAIN`, `INFERRED`, `UNCERTAIN`)
  - mismatches found, with severities for validator deduplication
  - coverage gaps that could not be inferred
- Do not continue to Step 4 while any file remains `PENDING` in on-disk manifest state.

### Step 4: Bug Detection

The main skill context must not perform bug detection itself. Use the `Task` tool to spawn `dimension-validator` agents to detect dimensional bugs in annotated code. For examples, red flags, rationalization checks, and standard vocabulary, see `[{baseDir}/references/bug-patterns.md]({baseDir}/references/bug-patterns.md)`, `[{baseDir}/references/common-dimensions.md]({baseDir}/references/common-dimensions.md)`, and `[{baseDir}/references/dimension-algebra.md]({baseDir}/references/dimension-algebra.md)`. DO NOT DETECT BUGS IN ANY OTHER STEP.

- Validate every file in `DIMENSIONAL_SCOPE.json.in_scope_files`.
- Use this priority order without skipping lower tiers:
  1. files with CRITICAL or HIGH Step 3 mismatches
  2. remaining CRITICAL and HIGH scanner-priority files
  3. remaining MEDIUM and LOW files
- Before launching validators, confirm every file already has a non-pending Step 3 status.
- Then set `step4 = "PENDING"` for every in-scope file and persist the updated manifest.
- Spawn one `dimension-validator` agent per file. For large repos, run them in waves of roughly 10-30 files to keep orchestration stable.
- Each validator prompt must include:
  - absolute path to `DIMENSIONAL_UNITS.md`
  - absolute path to `DIMENSIONAL_SCOPE.json`
  - the single file path to validate
  - a summary of anchor and propagated annotations in the file
  - Step 3 mismatch summaries for the file, including mismatch IDs
  - cross-file function signatures or return dimensions needed for call-boundary checks
  - required per-file status output: `VALIDATED` or `BLOCKED`
- After each wave, immediately persist each file to exactly one Step 4 status:
  - `VALIDATED`
  - `BLOCKED`
- If a file is `BLOCKED`, also persist `step4_reason` and `step4_retry_count`. Retry each `BLOCKED` file once with a focused prompt.
- Deduplicate findings:
  - confirmed Step 3 mismatches keep their original IDs and severities
  - refuted Step 3 mismatches are noted as false positives and excluded from final counts
  - genuinely new findings receive new `DIM-XXX` IDs
- Aggregate confirmed findings, new findings, refuted findings, coverage summary, and final `coverage.unprocessed_files`.
- Step 4 is complete only when `DIMENSIONAL_SCOPE.json.in_scope_files` contains no `step4: "PENDING"` entries.

## Reference Documentation

Pass these references to the relevant subagent when a step needs them:
- `[{baseDir}/references/dimension-algebra.md]({baseDir}/references/dimension-algebra.md)` - Propagator and validator algebra rules
- `[{baseDir}/references/common-dimensions.md]({baseDir}/references/common-dimensions.md)` - Validator vocabulary reference
- `[{baseDir}/references/bug-patterns.md]({baseDir}/references/bug-patterns.md)` - Validator bug-pattern and red-flag reference
- `[{baseDir}/references/annotate.md]({baseDir}/references/annotate.md)` - Annotator format and example reference

## Final Output

At the end of the analysis, provide a structured summary unless some other output format has been specified:

```json
{
  "mode": "full-auto",
  "project_root": "<path>",
  "vocabulary": {
    "base_units": ["..."],
    "derived_units": ["..."],
    "precision_prefixes": ["..."]
  },
  "annotations": {
    "total_added": 0,
    "by_file": {}
  },
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "details": []
  },
  "uncertainties_resolved": 0,
  "coverage": {
    "in_scope_files": 0,
    "anchor_reviewed_files": "0/0",
    "propagation_reviewed_files": "0/0",
    "validation_reviewed_files": "0/0",
    "annotated_functions": "0/0",
    "annotated_variables": "0/0",
    "unprocessed_files": [
      {
        "path": "/path/to/repo/contracts/LegacyMath.sol",
        "blocked_step": "step3",
        "reason": "Parser could not process generated source",
        "retry_count": 1
      }
    ]
  }
}
```

## Completion Checklist

You are NOT done until all of these are true:

### File Coverage Gates
- [ ] `DIMENSIONAL_UNITS.md` exists in the project root
- [ ] `DIMENSIONAL_SCOPE.json` exists in the project root and is the source of truth for downstream coverage
- [ ] Every in-scope arithmetic file discovered in Step 1 appears in `DIMENSIONAL_SCOPE.json.in_scope_files`
- [ ] Every in-scope file has a non-`PENDING` Step 2 status (`ANNOTATED`, `REVIEWED_NO_ANCHOR_CHANGES`, or `BLOCKED`)
- [ ] Every in-scope file has a non-`PENDING` Step 3 status (`PROPAGATED`, `REVIEWED_NO_PROPAGATION_CHANGES`, or `BLOCKED`)
- [ ] Every in-scope file has a non-`PENDING` Step 4 status (`VALIDATED` or `BLOCKED`)
- [ ] No in-scope file remains `PENDING` in any step
- [ ] Any `BLOCKED` file has a documented reason in the final output
- [ ] `coverage.unprocessed_files` exactly matches the final set of terminal `BLOCKED` files after retries, using `path`, `blocked_step`, `reason`, and `retry_count`

### Summary Report
- [ ] Final summary JSON/report provided
- [ ] Final coverage counters match `DIMENSIONAL_SCOPE.json`
- [ ] List of modified files provided when edits occurred
- [ ] Any dimensional mismatches or bugs found are summarized
- [ ] Any remaining blocked or unprocessed files are called out with reasons

**If `DIMENSIONAL_SCOPE.json` and the final report disagree, reconcile the report or continue processing until they match.**
**Do not claim completion from agent intent alone; completion is determined by manifest coverage and final reported statuses.**
