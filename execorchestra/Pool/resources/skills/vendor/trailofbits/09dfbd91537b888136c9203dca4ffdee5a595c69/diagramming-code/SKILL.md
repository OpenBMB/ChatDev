---
name: diagramming-code
description: >
  Generates Mermaid diagrams from Trailmark code graphs. Produces call graphs,
  class hierarchies, module dependency maps, containment diagrams, complexity
  heatmaps, and attack surface data flow visualizations. Use when visualizing
  code architecture, drawing call graphs, generating class diagrams, creating
  dependency maps, producing complexity heatmaps, or visualizing data flow
  and attack surface paths as Mermaid diagrams.
---

# Diagramming Code

Generates Mermaid diagrams from Trailmark's code graph. A pre-made script
handles Mermaid syntax generation; Claude selects the diagram type and
parameters. Trailmark 0.4.0 includes a native `trailmark diagram` command; use
it only after a version/command check, otherwise use this skill's bundled
script.

## When to Use

- Visualizing call paths between functions
- Drawing class inheritance hierarchies
- Mapping module import dependencies
- Showing class structure with members
- Highlighting complexity hotspots with color coding
- Tracing data flow from entrypoints to sensitive functions

## When NOT to Use

- Querying the graph without visualization (use the `trailmark` skill)
- Mutation testing triage (use the `genotoxic` skill)
- Architecture diagrams not derived from code (draw by hand)

## Prerequisites

**trailmark** must be installed. If `uv run trailmark` fails, run:

```bash
uv pip install trailmark
```

**DO NOT** fall back to hand-writing Mermaid from source code reading. The
script uses Trailmark's parsed graph for accuracy. If installation fails,
report the error to the user.

## Version Gate

Check whether native v0.4 diagram support exists:

```bash
trailmark diagram --help 2>/dev/null || uv run trailmark diagram --help 2>/dev/null
```

If this succeeds, you may use `trailmark diagram`. If it fails, use
`uv run {baseDir}/scripts/diagram.py`, which keeps the older skill workflow
intact. Do not assume the native CLI exists on Trailmark 0.2.x.

---

## Quick Start

```bash
uv run {baseDir}/scripts/diagram.py \
    --target {targetDir} --language auto --type call-graph \
    --focus main --depth 2

# Trailmark 0.4.0+ equivalent after the Version Gate succeeds
uv run trailmark diagram \
    --target {targetDir} --language auto --type call-graph \
    --focus main --depth 2
```

Output is raw Mermaid text. Wrap in a fenced code block:

````markdown
```mermaid
flowchart TB
    ...
```
````

---

## Diagram Types

```
├─ "Who calls what?"               → --type call-graph
├─ "Class inheritance?"             → --type class-hierarchy
├─ "Module dependencies?"           → --type module-deps
├─ "Class members and structure?"   → --type containment
├─ "Where is complexity highest?"   → --type complexity
└─ "Path from input to function?"   → --type data-flow
```

For detailed examples of each type, see
[references/diagram-types.md](references/diagram-types.md).

---

## Workflow

```
Diagram Progress:
- [ ] Step 1: Verify trailmark is installed
- [ ] Step 2: Identify diagram type from user request
- [ ] Step 3: Determine focus node and parameters
- [ ] Step 4: Run diagram.py script (or native trailmark diagram on v0.4+)
- [ ] Step 5: Verify output is non-empty and well-formed
- [ ] Step 6: Embed diagram in response
```

**Step 1:** Run `uv run trailmark analyze --language auto --summary {targetDir}`. Install
if it fails. Then run pre-analysis via the programmatic API:

```python
from trailmark.query.api import QueryEngine

engine = QueryEngine.from_directory("{targetDir}", language="auto")
engine.preanalysis()
```

Pre-analysis enriches the graph with blast radius, taint propagation,
and privilege boundary data used by `data-flow` diagrams.

If auto-detection is wrong for the target, rerun with an explicit language or
comma-separated list such as `python,rust`.

**Step 2:** Match the user's request to a `--type` using the decision tree
above.

**Step 3:** For `call-graph` and `data-flow`, identify the focus function.
Default `--depth 2`. Use `--direction LR` for dependency flows.

**Step 4:** Run the script and capture stdout.
If the native v0.4 CLI is available, either command is acceptable; prefer the
bundled script when you need behavior consistent with this skill's references.

**Step 5:** Check: output starts with `flowchart` or `classDiagram`,
contains at least one node. If empty or malformed, consult
[references/mermaid-syntax.md](references/mermaid-syntax.md).

**Step 6:** Wrap output in ` ```mermaid ``` ` code fence.

---

## Script Reference

```
uv run {baseDir}/scripts/diagram.py [OPTIONS]
# or, on Trailmark 0.4.0+:
uv run trailmark diagram [OPTIONS]
```

| Argument | Short | Default | Description |
|---|---|---|---|
| `--target` | `-t` | required | Directory to analyze |
| `--language` | `-l` | `python` | Source language |
| `--type` | `-T` | required | Diagram type (see above) |
| `--focus` | `-f` | none | Center diagram on this node |
| `--depth` | `-d` | `2` | BFS traversal depth |
| `--direction` | | `TB` | Layout: `TB` (top-bottom) or `LR` (left-right) |
| `--threshold` | | `10` | Min complexity for `complexity` type |

### Examples

```bash
# Call graph centered on a function
uv run {baseDir}/scripts/diagram.py -t src/ -T call-graph -f parse_file

# Class hierarchy for a Rust project
uv run {baseDir}/scripts/diagram.py -t src/ -l rust -T class-hierarchy

# Module dependency map, left-to-right
uv run {baseDir}/scripts/diagram.py -t src/ -T module-deps --direction LR

# Class members
uv run {baseDir}/scripts/diagram.py -t src/ -T containment

# Complexity heatmap (threshold 5)
uv run {baseDir}/scripts/diagram.py -t src/ -T complexity --threshold 5

# Data flow from entrypoints to a specific function
uv run {baseDir}/scripts/diagram.py -t src/ -T data-flow -f execute_query
```

---

## Customization

**Direction:** Use `TB` (default) for hierarchical views, `LR` for
left-to-right flows like dependency chains.

**Depth:** Increase `--depth` to see more of the call graph. Decrease to
reduce clutter. The script warns if the diagram exceeds 100 nodes.

**Focus:** Always use `--focus` for `call-graph` on non-trivial codebases.
For `data-flow`, omitting focus auto-targets the top 10 complexity hotspots.

**Language:** Prefer `--language auto` for polyglot or unfamiliar repos.
Use an explicit language only when you know the target is single-language or
you need to exclude unrelated components.

---

## Supporting Documentation

- **[references/diagram-types.md](references/diagram-types.md)** -
  Detailed docs and Mermaid examples for each diagram type
- **[references/mermaid-syntax.md](references/mermaid-syntax.md)** -
  ID sanitization, escaping, style definitions, and common pitfalls
