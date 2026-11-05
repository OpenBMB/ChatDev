---
name: query
description: "Search the FPF knowledge base and display hypothesis details with assurance information"
---

# Query Knowledge

Search the FPF knowledge base and display hypothesis details with assurance information.

## Action (Run-Time)

1. **Search** `.fpf/knowledge/` and `.fpf/decisions/` by user query.
2. **For each found hypothesis**, display:
   - Basic info: title, layer (L0/L1/L2), kind, scope
   - If layer >= L1: read audit section for R_eff
   - If has dependencies: show dependency graph
   - Evidence summary if exists
3. **Present results** in table format.

## Search Locations

| Location | Contents |
|----------|----------|
| `.fpf/knowledge/L0/` | Proposed hypotheses |
| `.fpf/knowledge/L1/` | Verified hypotheses |
| `.fpf/knowledge/L2/` | Validated hypotheses |
| `.fpf/knowledge/invalid/` | Rejected hypotheses |
| `.fpf/decisions/` | Design Rationale Records |
| `.fpf/evidence/` | Evidence and audit files |

## Output Format

```markdown
## Search Results for "<query>"

### Hypotheses Found

| Hypothesis | Layer | Kind | R_eff |
|------------|-------|------|-------|
| redis-caching | L2 | system | 0.85 |
| cdn-edge | L2 | system | 0.72 |

### redis-caching (L2)

**Title**: Use Redis for Caching
**Kind**: system
**Scope**: High-load systems, Linux only

**R_eff**: 0.85
**Weakest Link**: internal test (0.85)

**Dependencies**:
```
[redis-caching R:0.85]
  └── (no dependencies)
```

**Evidence**:
- ev-benchmark-redis-caching-2025-01-15 (internal, PASS)

### cdn-edge (L2)

**Title**: Use CDN Edge Cache
**Kind**: system
**Scope**: Static content delivery

**R_eff**: 0.72
**Weakest Link**: external docs (CL1 penalty)

**Evidence**:
- ev-research-cdn-2025-01-10 (external, PASS)
```

## Search Methods

### By Keyword

Search file contents for matching text:

```
/fpf:query caching
-> Finds all hypotheses with "caching" in title or content
```

### By Specific ID

Look up a specific hypothesis:

```
/fpf:query redis-caching
-> Shows full details for redis-caching
-> Displays dependency tree
-> Shows R_eff breakdown
```

### By Layer

Filter by knowledge layer:

```
/fpf:query L2
-> Lists all L2 hypotheses with R_eff scores
```

### By Decision

Search decision records:

```
/fpf:query DRR
-> Lists all Design Rationale Records
-> Shows what each DRR selected/rejected
```

## R_eff Display

For L1+ hypotheses, read the audit section and display:

```markdown
**R_eff Breakdown**:
- Self Score: 1.00
- Weakest Link: ev-research-redis (0.90)
- Dependency Penalty: none
- **Final R_eff**: 0.85
```

## Dependency Tree Display

If hypothesis has `depends_on`, show the tree:

```
[api-gateway R:0.80]
  └──(CL:3)── [auth-module R:0.85]
  └──(CL:2)── [rate-limiter R:0.90]
```

Legend:
- `R:X.XX` = R_eff score
- `CL:N` = Congruence Level (1-3)

## Examples

**Search by keyword:**
```
User: /fpf:query caching

Results:
| Hypothesis | Layer | R_eff |
|------------|-------|-------|
| redis-caching | L2 | 0.85 |
| cdn-edge-cache | L2 | 0.72 |
| lru-cache | invalid | N/A |
```

**Query specific hypothesis:**
```
User: /fpf:query redis-caching

# redis-caching (L2)

Title: Use Redis for Caching
Kind: system
Scope: High-load systems
R_eff: 0.85
Evidence: 2 files
```

**Query decisions:**
```
User: /fpf:query DRR

# Design Rationale Records

| DRR | Date | Winner | Rejected |
|-----|------|--------|----------|
| DRR-2025-01-15-caching | 2025-01-15 | redis-caching | cdn-edge |
```
