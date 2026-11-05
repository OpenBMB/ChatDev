# Mermaid Syntax Reference

Pitfalls and edge cases when generating Mermaid from code graph data.

## Contents

- [Node ID sanitization](#node-id-sanitization)
- [Label escaping](#label-escaping)
- [Style definitions](#style-definitions)
- [Edge confidence styling](#edge-confidence-styling)
- [Common pitfalls](#common-pitfalls)

---

## Node ID Sanitization

Trailmark node IDs use `module:Class.method` format. Mermaid node IDs
only allow `[a-zA-Z0-9_]`.

**Rules applied by `diagram.py`:**
- Replace any non-alphanumeric character (except `_`) with `_`
- Prefix with `n_` if the result starts with a digit

**Examples:**

| Trailmark ID | Mermaid ID |
|---|---|
| `query.api:QueryEngine.callers_of` | `query_api_QueryEngine_callers_of` |
| `3rdparty:init` | `n_3rdparty_init` |

---

## Label Escaping

Node labels are wrapped in double quotes to safely include special
characters:

```
    node_id["label with (parens) and: colons"]
```

If the label itself contains double quotes, replace `"` with `#quot;`
(Mermaid's HTML entity escape).

---

## Style Definitions

Use `classDef` to define reusable styles and `:::` to apply them:

```mermaid
flowchart TB
    A["Low complexity"]:::low
    B["High complexity"]:::high
    classDef low fill:rgba(40,167,69,0.2),stroke:#28a745,color:#28a745
    classDef high fill:rgba(220,53,69,0.2),stroke:#dc3545,color:#dc3545
```

The script defines three classes for complexity heatmaps:
- `low` (green): CC < 5
- `medium` (yellow): CC 5-10
- `high` (red): CC > 10

And one for data flow:
- `entrypoint` (blue): marks untrusted input sources

---

## Edge Confidence Styling

Arrow syntax varies by edge confidence:

| Confidence | Arrow | Meaning |
|---|---|---|
| `certain` | `-->` | Direct call or `self.method()` |
| `inferred` | `-.->` | Attribute access on non-self object |
| `uncertain` | `..->` | Dynamic dispatch, reflection |

For class diagrams, arrows are different:
- `<\|--` = inherits
- `<\|..` = implements

---

## Common Pitfalls

**Reserved words as node IDs:** `end`, `graph`, `subgraph`, `style`,
`classDef`, `click` are reserved. The sanitization function avoids most
conflicts since it replaces special characters, but single-word function
names matching reserved words can still collide. Workaround: use the full
qualified ID which includes the module prefix.

**Leading digits:** Mermaid node IDs cannot start with a digit. The
script prefixes `n_` in this case.

**Diagram size:** Mermaid renderers struggle with >100 nodes. The script
warns when this limit is exceeded and suggests using `--focus` to scope
the diagram.

**Empty diagrams:** When no edges of the required type exist (e.g., no
`inherits` edges in a Go codebase), the script emits a single-node
diagram with an explanatory message rather than failing.

**Parentheses in labels:** Mermaid interprets `()` as rounded-rectangle
node shape. Always use quoted labels (`["label"]`) to avoid accidental
shape changes.
