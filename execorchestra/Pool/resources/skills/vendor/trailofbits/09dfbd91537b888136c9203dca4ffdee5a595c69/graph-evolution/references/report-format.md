# Report Format Reference

Output format for graph-evolution reports. The report is a markdown file
summarizing structural changes between two code graph snapshots.

## Contents

- Report filename convention
- Section-by-section template
- Severity classification
- Example snippets

---

## Filename Convention

```
GRAPH_EVOLUTION_<project>_<before-ref>_<after-ref>.md
```

Example: `GRAPH_EVOLUTION_myapp_v1.2.0_v1.3.0.md`

---

## Report Template

```markdown
# Graph Evolution Report

**Project:** {project_name}
**Before:** {before_ref} ({before_date})
**After:** {after_ref} ({after_date})
**Language:** {language}

## Summary

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total nodes | N | N | +/-N |
| Functions | N | N | +/-N |
| Classes | N | N | +/-N |
| Call edges | N | N | +/-N |
| Entrypoints | N | N | +/-N |

## Critical Structural Changes

Changes with direct security implications. Each finding includes
the structural evidence and affected nodes.

### [SEVERITY] Finding title

**What changed:** Description of the structural change
**Evidence:** Node IDs, edge diffs, subgraph membership
**Security impact:** Why this matters
**Recommendation:** What to review or test

## Attack Surface Evolution

### New Entrypoints
| Node | Kind | Trust Level | File |
|------|------|------------|------|

### Removed Entrypoints
| Node | Kind | Trust Level | File |
|------|------|------------|------|

## Complexity Evolution

### Increased Complexity (CC delta > 0)
| Node | Before CC | After CC | Delta | File |
|------|-----------|----------|-------|------|

### Decreased Complexity (CC delta < 0)
| Node | Before CC | After CC | Delta | File |
|------|-----------|----------|-------|------|

## Taint Propagation Changes

### Newly Tainted Nodes
| Node | Kind | Tainted Via | File |
|------|------|-------------|------|

### De-Tainted Nodes
| Node | Kind | File |
|------|------|------|

## Blast Radius Shifts

### Nodes Entering high_blast_radius
| Node | Kind | Downstream Count | File |
|------|------|-----------------|------|

### Nodes Leaving high_blast_radius
| Node | Kind | File |
|------|------|------|

## Privilege Boundary Changes

### New Boundary Crossings
| Node | Trust Transition | File |
|------|-----------------|------|

### Removed Boundary Crossings
| Node | Trust Transition | File |
|------|-----------------|------|

## New Code (Added Nodes)
| Node | Kind | CC | File |
|------|------|----|------|

## Removed Code (Deleted Nodes)
| Node | Kind | CC | File |
|------|------|----|------|

## New Call Relationships (Added Edges)
| Source | Target | Kind |
|--------|--------|------|

## Removed Call Relationships (Deleted Edges)
| Source | Target | Kind |
|--------|--------|------|

## Methodology

- **Tool:** Trailmark graph-evolution
- **Before snapshot:** {before_ref}
- **After snapshot:** {after_ref}
- **Pre-analysis:** blast radius, taint, privilege boundaries,
  entrypoints
- **Limitations:** {honest scope disclosure}
```

---

## Severity Classification

Classify structural findings by security impact:

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | New tainted path to sensitive function, removed auth boundary |
| **HIGH** | New entrypoint + high blast radius, CC increase > 10 on tainted node |
| **MEDIUM** | New call edges crossing trust boundaries, moderate CC increase |
| **LOW** | Added nodes without entrypoint reachability, cosmetic changes |
| **INFO** | Dead code removal, complexity reductions, positive changes |

---

## Example: Critical Finding

```markdown
### [CRITICAL] New untrusted path to database query

**What changed:** Function `parse_user_input` (added) calls
`execute_query` (existing, tainted). This edge did not exist in the
before snapshot.

**Evidence:**
- Added edge: `parse_user_input` → `execute_query` (calls, certain)
- `execute_query` is in `high_blast_radius` (47 downstream nodes)
- `parse_user_input` is in `tainted` subgraph
- `parse_user_input` CC = 12 (above fuzzing threshold)

**Security impact:** Untrusted external input can now reach database
query execution through a complex, high-blast-radius path.

**Recommendation:**
1. Verify input validation on `parse_user_input`
2. Add parameterized query usage in `execute_query`
3. Write fuzz harness targeting `parse_user_input`
```
