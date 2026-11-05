---
name: decay
description: "Manage evidence freshness by identifying stale decisions and providing governance actions"
---

# Evidence Freshness Management

Manages **evidence freshness** by identifying stale decisions and providing governance actions. Implements FPF B.3.4 (Evidence Decay).

**Key principle:** Evidence is perishable. Decisions built on expired evidence carry hidden risk.

---

## Quick Concepts

### What is "stale" evidence?

Every piece of evidence has a `valid_until` date. A benchmark from 6 months ago may no longer reflect current system performance. A security audit from before a major dependency update doesn't account for new vulnerabilities.

When evidence expires, the decision it supports becomes **questionable** - not necessarily wrong, just unverified.

### What is "waiving"?

**Waiving = "I know this evidence is stale, I accept the risk temporarily."**

Use it when:
- You're about to launch and don't have time to re-run all tests
- The evidence is only slightly expired and probably still valid
- You have a scheduled date to refresh it properly

A waiver is NOT ignoring the problem - it's **explicitly documenting** that you know about the risk and accept it until a specific date.

### The Three Actions

| Situation | Action | What it does |
|-----------|--------|--------------|
| Evidence is old but decision is still good | **Refresh** | Re-run the test, get fresh evidence |
| Decision is obsolete, needs rethinking | **Deprecate** | Downgrade hypothesis, restart evaluation |
| Accept risk temporarily | **Waive** | Record the risk acceptance with deadline |

---

## Action (Run-Time)

### Step 1: Generate Freshness Report

1. List all evidence files in `.fpf/evidence/`
2. For each evidence file:
   - Read `valid_until` from frontmatter
   - Compare with current date
   - Classify as FRESH, STALE, or EXPIRED

### Step 2: Present Report

```markdown
## Evidence Freshness Report

### EXPIRED (Requires Action)

| Evidence | Hypothesis | Expired | Days Overdue |
|----------|------------|---------|--------------|
| ev-benchmark-2024-06-15 | redis-caching | 2024-12-15 | 45 |
| ev-security-2024-07-01 | auth-module | 2025-01-01 | 14 |

### STALE (Warning)

| Evidence | Hypothesis | Expires | Days Left |
|----------|------------|---------|-----------|
| ev-loadtest-2024-10-01 | api-gateway | 2025-01-20 | 5 |

### FRESH

| Evidence | Hypothesis | Expires |
|----------|------------|---------|
| ev-unittest-2025-01-10 | validation-lib | 2025-07-10 |

### WAIVED

| Evidence | Waived Until | Rationale |
|----------|--------------|-----------|
| ev-perf-old | 2025-02-01 | Migration pending |
```

### Step 3: Handle User Actions

Based on user response, perform one of:

#### Refresh

User: "Refresh the redis caching evidence"

1. Navigate to the hypothesis in `.fpf/knowledge/L2/`
2. Re-run validation to create fresh evidence

#### Deprecate

User: "Deprecate the auth module decision"

1. Move hypothesis from L2 to L1 (or L1 to L0)
2. Create deprecation record:

```markdown
# In .fpf/evidence/deprecate-auth-module-2025-01-15.md
---
id: deprecate-auth-module-2025-01-15
hypothesis_id: auth-module
action: deprecate
from_layer: L2
to_layer: L1
created: 2025-01-15T10:00:00Z
---

# Deprecation: auth-module

**Reason**: Evidence expired, technology landscape changed

**Next Steps**: Run `/fpf:propose-hypotheses` to explore alternatives
```

3. Move the hypothesis file:
```bash
mv .fpf/knowledge/L2/auth-module.md .fpf/knowledge/L1/auth-module.md
```

#### Waive

User: "Waive the benchmark until February"

1. Create waiver record:

```markdown
# In .fpf/evidence/waiver-benchmark-2025-01-15.md
---
id: waiver-benchmark-2025-01-15
evidence_id: ev-benchmark-2024-06-15
waived_until: 2025-02-01
created: 2025-01-15T10:00:00Z
---

# Waiver: ev-benchmark-2024-06-15

**Evidence**: ev-benchmark-2024-06-15
**Hypothesis**: redis-caching
**Waived Until**: 2025-02-01
**Rationale**: Migration pending, will re-run after completion

**Accepted By**: User
**Created**: 2025-01-15

**WARNING**: This evidence returns to EXPIRED status after 2025-02-01.
```

---

## Natural Language Usage

**You don't need to memorize evidence IDs.** Just describe what you want.

### Example Workflow

```
User: /fpf:decay

Agent shows report with stale evidence

User: Waive the benchmark until February, we'll re-run it after the migration.

Agent: Creating waiver for ev-benchmark-2024-06-15 until 2025-02-01.
       Rationale: "Re-run after migration"

       [Creates .fpf/evidence/waiver-benchmark-2025-01-15.md]

User: The vendor API is being discontinued. Deprecate that decision.

Agent: Deprecating hypothesis-vendor-api from L2 to L1.
       [Moves file, creates deprecation record]

       Next step: Run /fpf:propose-hypotheses to explore alternatives.
```

---

## WLNK Principle

A hypothesis is **STALE** if *any* of its evidence is expired (and not waived).

This is the Weakest Link (WLNK) principle: reliability = min(all evidence). One stale piece makes the whole decision questionable.

---

## Audit Trail

All actions are logged:

| Action | What's Recorded |
|--------|-----------------|
| Deprecate | from_layer, to_layer, reason, date |
| Waive | evidence_id, until_date, rationale, date |

Files created in `.fpf/evidence/`:
- `deprecate-{hypothesis}-{date}.md`
- `waiver-{evidence}-{date}.md`

---

## Common Workflows

### Weekly Maintenance
```
/fpf:decay                    # See what's stale
# For each stale item: refresh, deprecate, or waive
```

### Pre-Release
```
/fpf:decay                    # Check for stale decisions
# Either refresh evidence or explicitly waive with documented rationale
# Waiver rationales become part of release documentation
```

### After Major Change
```
# Dependency update, API change, security advisory...
/fpf:decay                    # See what's affected
# Deprecate obsolete decisions
# Start new hypothesis cycle for replacements
```
