# Variant Analysis Report

## Summary

| Field | Value |
|-------|-------|
| **Original Bug** | [BUG_ID / CVE] |
| **Analysis Date** | [DATE] |
| **Codebase** | [REPO/PROJECT] |
| **Variants Found** | [COUNT] |

## Original Vulnerability

**Root Cause:** [e.g., "User input reaches SQL query without parameterization"]

**Location:** `[path/to/file.py:LINE]` in `function_name()`

```python
# Vulnerable code
```

## Search Methodology

| Version | Pattern | Tool | Matches | TP | FP |
|---------|---------|------|---------|----|----|
| v1 | [exact] | ripgrep | 1 | 1 | 0 |
| v2 | [abstract] | semgrep | N | N | N |

**Final Pattern:**
```yaml
# Pattern used
```

## Findings

### Variant #1: [BRIEF_TITLE]

| Severity | Confidence | Status |
|----------|------------|--------|
| High | High | Confirmed |

**Location:** `[path/to/file.py:LINE]`

```python
# Vulnerable code
```

**Analysis:** [Why this is a true/false positive]

**Exploitability:**
- [ ] Reachable from external input
- [ ] User-controlled data
- [ ] No sanitization

---

<!-- Copy variant template above for additional findings -->

## False Positive Patterns

| Pattern | Count | Reason |
|---------|-------|--------|
| [pattern] | N | [why safe] |

## Recommendations

### Immediate
1. Fix variant in [location]

### Preventive
1. Add Semgrep rule to CI

```yaml
# CI-ready rule
```
