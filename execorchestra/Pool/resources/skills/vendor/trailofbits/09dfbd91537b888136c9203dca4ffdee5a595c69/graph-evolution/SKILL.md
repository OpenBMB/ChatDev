---
name: graph-evolution
description: >
  Compares Trailmark code graphs at two source code snapshots (git commits,
  tags, or directories) to surface security-relevant structural changes.
  Detects new attack paths, complexity shifts, blast radius growth, taint
  propagation changes, and privilege boundary modifications that text diffs
  miss. Use when comparing code between commits or tags, analyzing structural
  evolution, detecting attack surface growth, reviewing what changed between
  audit snapshots, or finding security-relevant changes that text diffs miss.
---

# Graph Evolution

Builds Trailmark code graphs at two source snapshots and computes a
structural diff. Surfaces security-relevant changes that text-level
diffs miss: new attack paths, complexity shifts, blast radius growth,
taint propagation changes, and privilege boundary modifications.

## When to Use

- Comparing two git refs to understand what structurally changed
- Auditing a range of commits for security-relevant evolution
- Detecting new attack paths created by code changes
- Finding functions whose blast radius or complexity grew silently
- Identifying taint propagation changes across refactors
- Pre-release structural comparison (tag-to-tag or branch-to-branch)

## When NOT to Use

- Line-level code review (use `differential-review` for text-diff analysis)
- Single-snapshot analysis (use the `trailmark` skill directly)
- Diagram generation from a single snapshot (use the `diagramming-code` skill)
- Mutation testing triage (use the `genotoxic` skill)

## Rationalizations to Reject

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "We just need the structural diff, skip pre-analysis" | Without pre-analysis, you miss taint changes, blast radius growth, and privilege boundary shifts | Run `engine.preanalysis()` on both snapshots |
| "Text diff covers what changed" | Text diffs miss new attack paths, transitive complexity shifts, and subgraph membership changes | Use structural diff to complement text diff |
| "Only added nodes matter" | Removed security functions and shifted privilege boundaries are equally dangerous | Review removals and modifications, not just additions |
| "Low-severity structural changes can be ignored" | INFO-level changes (dead code removal) can mask removed security checks | Classify every change, review removals for replaced functionality |
| "One snapshot's graph is enough for comparison" | Single-snapshot analysis can't detect evolution — you need both before and after | Always build and export both graphs |
| "Tool isn't installed, I'll compare manually" | Manual comparison misses what graph analysis catches | Install trailmark first |

---

## Prerequisites

**trailmark** must be installed. If `uv run trailmark` fails, run:

```bash
uv pip install trailmark
```

**DO NOT** fall back to "manual comparison" or reading source files as a
substitute for running trailmark. The tool must be installed and used
programmatically. If installation fails, report the error.

---

## Quick Start

```bash
# Compare two git refs (e.g., tags, branches, commits)
# 1. Build graphs at each snapshot
# 2. Run pre-analysis on both
# 3. Compute structural diff
# 4. Generate report

# Step-by-step: see Workflow below
```

---

## Decision Tree

```
├─ Need to understand what each metric means?
│  └─ Read: references/evolution-metrics.md
│
├─ Need the report output format?
│  └─ Read: references/report-format.md
│
├─ Already have two graph JSON exports?
│  └─ Jump to Phase 3 (run native diff + graph_diff.py)
│
└─ Starting from two git refs?
   └─ Start at Phase 1
```

---

## Workflow

```
Graph Evolution Progress:
- [ ] Phase 1: Create snapshots (git worktrees)
- [ ] Phase 2: Build graphs + pre-analysis on both snapshots
- [ ] Phase 3: Compute structural diff
- [ ] Phase 4: Interpret diff and generate report
- [ ] Phase 5: Clean up worktrees
```

### Phase 1: Create Snapshots

Use git worktrees to get clean copies of each ref without disturbing
the working tree.

```bash
# Create temp directories for worktrees
BEFORE_DIR=$(mktemp -d)
AFTER_DIR=$(mktemp -d)

# Create worktrees (run from repo root)
git worktree add "$BEFORE_DIR" {before_ref}
git worktree add "$AFTER_DIR" {after_ref}
```

If comparing two directories instead of git refs, skip this phase and
use the directory paths directly in Phase 2.

### Phase 2: Build Graphs and Run Pre-Analysis

Build Trailmark graphs for both snapshots and run pre-analysis on each.
Pre-analysis computes blast radius, taint propagation, privilege
boundaries, and entrypoint enumeration.

```python
from trailmark.query.api import QueryEngine

def build_and_export(target_dir, output_path, language="auto"):
    """Build graph, run pre-analysis, export JSON."""
    engine = QueryEngine.from_directory(target_dir, language=language)
    engine.preanalysis()
    json_str = engine.to_json()
    with open(output_path, "w") as f:
        f.write(json_str)
    return engine.summary()

import tempfile, os
work_dir = tempfile.mkdtemp(prefix="trailmark_evolution_")
before_json = os.path.join(work_dir, "before_graph.json")
after_json = os.path.join(work_dir, "after_graph.json")

before_summary = build_and_export(
    "{before_dir}", before_json
)
after_summary = build_and_export(
    "{after_dir}", after_json
)
```

Verify both graphs built successfully by checking the summary output.
If either fails, rerun with an explicit language or comma-separated list
instead of `auto`.

### Phase 3: Compute Structural Diff

Run **both**:

1. Trailmark's native structural diff for nodes, edges, and entrypoints
2. The plugin's `graph_diff.py` helper for subgraph membership changes

Using the same `work_dir` from Phase 2:

```bash
trailmark diff --json "{before_dir}" "{after_dir}" > "{work_dir}/trailmark_diff.json" || \
  uv run trailmark diff --json "{before_dir}" "{after_dir}" > "{work_dir}/trailmark_diff.json"

uv run {baseDir}/scripts/graph_diff.py \
    --before "{before_json}" \
    --after "{after_json}" > "{work_dir}/subgraph_diff.json"
```

If either diff command fails or writes an empty JSON file, stop and report the
error instead of continuing to Phase 4.

The native Trailmark diff contains:

| Key | Contents |
|-----|----------|
| `summary_delta` | Changes in node/edge/entrypoint counts |
| `nodes.added` | New functions, classes, methods |
| `nodes.removed` | Deleted functions, classes, methods |
| `nodes.modified` | Functions with changed CC, params, line span |
| `edges.added` | New call/inheritance/import relationships |
| `edges.removed` | Deleted relationships |
| `entrypoints` | Added, removed, and modified entrypoints |

The subgraph diff contains:

| Key | Contents |
|-----|----------|
| `subgraphs` | Per-subgraph membership changes (tainted, high_blast_radius, etc.) |

### Phase 4: Interpret Diff and Generate Report

Read **both** diff JSON files and generate a security-focused markdown
report.
See [references/report-format.md](references/report-format.md) for
the full template.

**Interpretation priorities (highest to lowest):**

1. **New tainted paths** — nodes entering the `tainted` subgraph,
   especially if they also appear in added edges targeting sensitive
   functions
2. **Privilege boundary changes** — new or removed trust transitions
   from the native entrypoint/edge diff plus the subgraph diff
3. **Attack surface growth** — new entrypoints, especially
   `untrusted_external`, from `trailmark_diff.json`
4. **Blast radius increases** — nodes entering `high_blast_radius`
5. **Complexity spikes** — CC increases > 3 on tainted or
   entrypoint-reachable nodes
6. **Structural additions** — new nodes and edges (review needed)
7. **Structural removals** — verify removed security functions were
   replaced

Cross-reference structural changes with `git diff {before_ref}..{after_ref}`
to add source-level context to findings.

**Severity classification:**

| Severity | Structural Signal |
|----------|------------------|
| CRITICAL | New tainted path to sensitive function, removed auth boundary |
| HIGH | New entrypoint + high blast radius, large CC increase on tainted node |
| MEDIUM | New trust-boundary-crossing edges, moderate CC increase |
| LOW | Added nodes without entrypoint reachability |
| INFO | Dead code removal, complexity reductions |

For detailed metric definitions, see
[references/evolution-metrics.md](references/evolution-metrics.md).

### Phase 5: Clean Up

Remove git worktrees after the report is written:

```bash
git worktree remove "{before_dir}"
git worktree remove "{after_dir}"
```

---

## Diff Reference

```
trailmark diff --json BEFORE AFTER
uv run {baseDir}/scripts/graph_diff.py [OPTIONS]
```

Use `trailmark diff` for:
- Node/edge changes
- Added/removed/modified entrypoints
- Human-readable structural diff reports

Use `graph_diff.py` for:
- Subgraph membership changes derived from `engine.preanalysis()`
- `tainted`, `high_blast_radius`, `privilege_boundary`, and related sets

| Argument | Default | Description |
|----------|---------|-------------|
| `--before` | required | Path to the "before" graph JSON |
| `--after` | required | Path to the "after" graph JSON |
| `--indent` | `2` | JSON output indentation |

`graph_diff.py` input format: Trailmark JSON exports from `engine.to_json()`.
`graph_diff.py` output: JSON structural diff for nodes, edges, and subgraphs.

---

## Quality Checklist

Before delivering the report:

- [ ] Both graphs built successfully (check summaries)
- [ ] Pre-analysis ran on both snapshots
- [ ] Native Trailmark diff computed and non-empty (`trailmark_diff.json`)
- [ ] Subgraph diff computed and non-empty (`subgraph_diff.json`)
- [ ] All subgraph changes interpreted (tainted, blast radius, etc.)
- [ ] Critical findings include evidence (node IDs, edge diffs)
- [ ] Severity levels assigned to all findings
- [ ] Source-level context added via git diff cross-reference
- [ ] Worktrees cleaned up (or temp dirs removed)
- [ ] Report written to `GRAPH_EVOLUTION_*.md`

---

## Integration

**trailmark skill:**
Phase 2 uses the trailmark API for graph building and pre-analysis.
All trailmark query patterns work on either snapshot's engine.

**differential-review skill:**
Use graph-evolution for structural analysis, differential-review for
line-level code review. The two are complementary — graph-evolution
finds attack paths that text diffs miss, while differential-review
provides git blame context and micro-adversarial analysis.

**trailmark-review-gate skill:**
Use trailmark-review-gate after graph-evolution when a branch, pull request,
fix commit, or release diff needs a PASS/WARN/FAIL/UNKNOWN structural review
packet. The gate applies deterministic review rules to graph-evolution output;
it does not replace human review.

**genotoxic skill:**
If graph-evolution reveals new high-CC tainted nodes, feed them to
genotoxic for mutation testing triage.

**diagramming-code skill:**
Generate before/after diagrams to visualize structural changes.
Use `call-graph` or `data-flow` diagrams focused on changed nodes.

---

## Supporting Documentation

- **[references/evolution-metrics.md](references/evolution-metrics.md)** —
  What each structural metric means and why it matters for security
- **[references/report-format.md](references/report-format.md)** —
  Report template, severity classification, and example findings
