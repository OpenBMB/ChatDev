---
name: audit-augmentation
description: >
  Augments Trailmark code graphs with external audit findings from SARIF static
  analysis results, weAudit annotation files, and version-gated Trailmark 0.4.x
  binary-analysis graph exports. Maps findings to graph nodes by
  file and line overlap, creates severity-based subgraphs, and enables
  cross-referencing findings with pre-analysis data (blast radius, taint, etc.).
  Use when projecting SARIF results onto a code graph, overlaying weAudit
  annotations, importing binary graph findings, cross-referencing Semgrep,
  CodeQL, or binary-analysis findings with call graph data, or visualizing audit
  findings in the context of code structure.
---

# Audit Augmentation

Projects findings from external tools (SARIF) and human auditors (weAudit)
onto Trailmark code graphs as annotations and subgraphs. Trailmark 0.4.0+ can
also import an external binary-analysis graph JSON export via
`engine.augment_binary()`.

## When to Use

- Importing Semgrep, CodeQL, or other SARIF-producing tool results into a graph
- Importing weAudit audit annotations into a graph
- Importing binary-analysis graph data into a source graph (Trailmark 0.4.0+)
- Cross-referencing static analysis findings with blast radius or taint data
- Querying which functions have high-severity findings
- Visualizing audit coverage alongside code structure
- Preparing one SARIF or weAudit result for `trailmark-finding-triage`

## When NOT to Use

- Running static analysis tools (use semgrep/codeql directly, then import)
- Building the code graph itself (use the `trailmark` skill)
- Generating diagrams (use the `diagramming-code` skill after augmenting)

## Rationalizations to Reject

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The user only asked about SARIF, skip pre-analysis" | Without pre-analysis, you can't cross-reference findings with blast radius or taint | Always run `engine.preanalysis()` before augmenting |
| "Unmatched findings don't matter" | Unmatched findings may indicate parsing gaps or out-of-scope files | Report unmatched count and investigate if high |
| "One severity subgraph is enough" | Different severities need different triage workflows | Query all severity subgraphs, not just `error` |
| "SARIF results speak for themselves" | Findings without graph context lack blast radius and taint reachability | Cross-reference with pre-analysis subgraphs |
| "weAudit and SARIF overlap, pick one" | Human auditors and tools find different things | Import both when available |
| "Tool isn't installed, I'll do it manually" | Manual analysis misses what tooling catches | Install trailmark first |

---

## Installation

**MANDATORY:** If `uv run trailmark` fails, install trailmark first:

```bash
uv pip install trailmark
```

## Version Gate

SARIF and weAudit augmentation are v0.2-safe. Binary graph augmentation is
Trailmark 0.4.0+ only. Before calling `engine.augment_binary()`, check:

```python
if not hasattr(engine, "augment_binary"):
    raise RuntimeError("Binary augmentation requires Trailmark >= 0.4.0")
```

On Trailmark 0.5.0+, known links between source functions and imported binary
or external endpoints can also be declared once in `.trailmark/links.toml`
(see the main `trailmark` skill's Repository Links section) instead of being
re-derived per session. Declared external endpoints materialize as
`proxy.external:<symbol>` nodes on every parse.

## Quick Start

### CLI

```bash
# Augment with SARIF
uv run trailmark augment {targetDir} --sarif results.sarif

# Augment with weAudit
uv run trailmark augment {targetDir} --weaudit .vscode/alice.weaudit

# Both at once, output JSON
uv run trailmark augment {targetDir} \
    --sarif results.sarif \
    --weaudit .vscode/alice.weaudit \
    --json
```

Binary graph augmentation is programmatic in Trailmark 0.4.0+; do not invent a
CLI flag if `trailmark augment --help` does not show one.

### Programmatic API

```python
from trailmark.query.api import QueryEngine

engine = QueryEngine.from_directory("{targetDir}", language="auto")

# Run pre-analysis first for cross-referencing
engine.preanalysis()

# Augment with SARIF
result = engine.augment_sarif("results.sarif")
# result: {matched_findings: 12, unmatched_findings: 3, subgraphs_created: [...]}

# Augment with weAudit
result = engine.augment_weaudit(".vscode/alice.weaudit")

# Augment with an external binary graph export (v0.4+)
if hasattr(engine, "augment_binary"):
    result = engine.augment_binary("binary_graph.json")

# Query findings
engine.findings()                                       # All findings
engine.subgraph("sarif:error")                          # High-severity SARIF
engine.subgraph("weaudit:high")                         # High-severity weAudit
engine.subgraph("sarif:semgrep")                        # By tool name
engine.annotations_of("function_name")                  # Per-node lookup
```

If auto-detection is wrong for the target, rerun with an explicit language or
comma-separated list such as `python,rust`.

## Workflow

```
Augmentation Progress:
- [ ] Step 1: Build graph and run pre-analysis
- [ ] Step 2: Locate SARIF/weAudit/binary graph files
- [ ] Step 3: Run augmentation
- [ ] Step 4: Inspect results and subgraphs
- [ ] Step 5: Cross-reference with pre-analysis
```

**Step 1:** Build the graph and run pre-analysis for blast radius and taint
context:

```python
engine = QueryEngine.from_directory("{targetDir}", language="auto")
engine.preanalysis()
```

If auto-detection is wrong for the target, rerun with an explicit language or
comma-separated list such as `python,rust`.

**Step 2:** Locate input files:
- **SARIF**: Usually output by tools like `semgrep --sarif -o results.sarif`
  or `codeql database analyze --format=sarif-latest`
- **weAudit**: Stored in `.vscode/<username>.weaudit` within the workspace
- **Binary graph (v0.4+)**: External JSON with `artifact`, `functions`, and
  `calls` fields. Trailmark imports this graph; it does not disassemble
  binaries itself.

**Step 3:** Run augmentation via `engine.augment_sarif()` or
`engine.augment_weaudit()`. For binary graphs, run `engine.augment_binary()`
only after the Version Gate succeeds. Check `unmatched_findings` in SARIF and
weAudit results — these are findings whose file/line locations didn't overlap
any parsed code unit.

**Step 4:** Query findings and subgraphs. Use `engine.findings()` to list all
annotated nodes. Use `engine.subgraph_names()` to see available subgraphs.

**Step 5:** Cross-reference with pre-analysis data to prioritize:
- Findings on tainted nodes: overlap `sarif:error` with `tainted` subgraph
- Findings on high blast radius nodes: overlap with `high_blast_radius`
- Findings on privilege boundaries: overlap with `privilege_boundary`

For one candidate finding that needs a reachability verdict or PoC handoff,
continue with `trailmark-finding-triage` and use the augmented node as the
bound candidate.

## Annotation Format

Findings are stored as standard Trailmark annotations:

- **Kind**: `finding` (tool-generated) or `audit_note` (human notes)
- **Source**: `sarif:<tool_name>` or `weaudit:<author>`
- **Description**: Compact single-line:
  `[SEVERITY] rule-id: message (tool)`

## Subgraphs Created

| Subgraph | Contents |
|----------|----------|
| `sarif:error` | Nodes with SARIF error-level findings |
| `sarif:warning` | Nodes with SARIF warning-level findings |
| `sarif:note` | Nodes with SARIF note-level findings |
| `sarif:<tool>` | Nodes flagged by a specific tool |
| `weaudit:high` | Nodes with high-severity weAudit findings |
| `weaudit:medium` | Nodes with medium-severity weAudit findings |
| `weaudit:low` | Nodes with low-severity weAudit findings |
| `weaudit:findings` | All weAudit findings (entryType=0) |
| `weaudit:notes` | All weAudit notes (entryType=1) |
| `binary:<artifact>` | Binary function nodes imported from a v0.4+ binary graph |

## How Matching Works

Findings are matched to graph nodes by file path and line range overlap:

1. Finding file path is normalized relative to the graph's `root_path`
2. Nodes whose `location.file_path` matches AND whose line range overlaps are
   selected
3. The tightest match (smallest span) is preferred
4. If a finding's location doesn't overlap any node, it counts as unmatched

SARIF paths may be relative, absolute, or `file://` URIs — all are handled.
weAudit uses 0-indexed lines which are converted to 1-indexed automatically.

Binary graph imports create `origin=binary` function nodes, `origin=proxy`
external proxy nodes for unresolved binary calls, and inferred
`corresponds_to` edges when a binary function maps back to a source node. The
expected JSON shape is intentionally small:

```json
{
  "artifact": {"name": "libexample", "architecture": "x86_64", "sha256": "..."},
  "functions": [
    {"symbol": "parse_packet", "address": "0x401000",
     "source": {"file": "src/parser.c", "line": 42}}
  ],
  "calls": [
    {"source": "parse_packet", "target": "malloc", "confidence": "inferred"}
  ]
}
```

## Supporting Documentation

- **[references/formats.md](references/formats.md)** — SARIF 2.1.0 and
  weAudit file format field reference
