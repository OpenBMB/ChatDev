---
name: plan-do-check-act
description: Iterative PDCA cycle for systematic experimentation and continuous improvement
argument-hint: Optional improvement goal or problem to address
---

# Plan-Do-Check-Act (PDCA)

Apply PDCA cycle for continuous improvement through iterative problem-solving and process optimization.

## Description

Four-phase iterative cycle: Plan (identify and analyze), Do (implement changes), Check (measure results), Act (standardize or adjust). Enables systematic experimentation and improvement.

## Usage

`/plan-do-check-act [improvement_goal]`

## Variables

- GOAL: Improvement target or problem to address (default: prompt for input)
- CYCLE_NUMBER: Which PDCA iteration (default: 1)

## Steps

### Phase 1: PLAN

1. Define the problem or improvement goal
2. Analyze current state (baseline metrics)
3. Identify root causes (use `/why` or `/cause-and-effect`)
4. Develop hypothesis: "If we change X, Y will improve"
5. Design experiment: what to change, how to measure success
6. Set success criteria (measurable targets)

### Phase 2: DO

1. Implement the planned change (small scale first)
2. Document what was actually done
3. Record any deviations from plan
4. Collect data throughout implementation
5. Note unexpected observations

### Phase 3: CHECK

1. Measure results against success criteria
2. Compare to baseline (before vs. after)
3. Analyze data: did hypothesis hold?
4. Identify what worked and what didn't
5. Document learnings and insights

### Phase 4: ACT

1. **If successful**: Standardize the change
   - Update documentation
   - Train team
   - Create checklist/automation
   - Monitor for regression
2. **If unsuccessful**: Learn and adjust
   - Understand why it failed
   - Refine hypothesis
   - Start new PDCA cycle with adjusted plan
3. **If partially successful**:
   - Standardize what worked
   - Plan next cycle for remaining issues

## Examples

### Example 1: Reducing Build Time

```
CYCLE 1
───────
PLAN:
  Problem: Docker build takes 45 minutes
  Current State: Full rebuild every time, no layer caching
  Root Cause: Package manager cache not preserved between builds
  Hypothesis: Caching dependencies will reduce build to <10 minutes
  Change: Add layer caching for package.json + node_modules
  Success Criteria: Build time <10 minutes on unchanged dependencies

DO:
  - Restructured Dockerfile: COPY package*.json before src files
  - Added .dockerignore for node_modules
  - Configured CI cache for Docker layers
  - Tested on 3 builds

CHECK:
  Results:
    - Unchanged dependencies: 8 minutes ✓ (was 45)
    - Changed dependencies: 12 minutes (was 45)
    - Fresh builds: 45 minutes (same, expected)
  Analysis: 82% reduction on cached builds, hypothesis confirmed

ACT:
  Standardize:
    ✓ Merged Dockerfile changes
    ✓ Updated CI pipeline config
    ✓ Documented in README
    ✓ Added build time monitoring
  
  New Problem: 12 minutes still slow when deps change
  → Start CYCLE 2


CYCLE 2
───────
PLAN:
  Problem: Build still 12 min when dependencies change
  Current State: npm install rebuilds all packages
  Root Cause: Some packages compile from source
  Hypothesis: Pre-built binaries will reduce to <5 minutes
  Change: Use npm ci instead of install, configure binary mirrors
  Success Criteria: Build <5 minutes on dependency changes

DO:
  - Changed to npm ci (uses package-lock.json)
  - Added .npmrc with binary mirror configs
  - Tested across 5 dependency updates

CHECK:
  Results:
    - Dependency changes: 4.5 minutes ✓ (was 12)
    - Compilation errors reduced to 0 (was 3)
  Analysis: npm ci faster + more reliable, hypothesis confirmed

ACT:
  Standardize:
    ✓ Use npm ci everywhere (local + CI)
    ✓ Committed .npmrc
    ✓ Updated developer onboarding docs
  
  Total improvement: 45min → 4.5min (90% reduction)
  ✓ PDCA complete, monitor for 2 weeks
```

### Example 2: Reducing Production Bugs

```
CYCLE 1
───────
PLAN:
  Problem: 8 production bugs per month
  Current State: Manual testing only, no automated tests
  Root Cause: Regressions not caught before release
  Hypothesis: Adding integration tests will reduce bugs by 50%
  Change: Implement integration test suite for critical paths
  Success Criteria: <4 bugs per month after 1 month

DO:
  Week 1-2: Wrote integration tests for:
    - User authentication flow
    - Payment processing
    - Data export
  Week 3: Set up CI to run tests
  Week 4: Team training on test writing
  Coverage: 3 critical paths (was 0)

CHECK:
  Results after 1 month:
    - Production bugs: 6 (was 8)
    - Bugs caught in CI: 4
    - Test failures (false positives): 2
  Analysis: 25% reduction, not 50% target
  Insight: Bugs are in areas without tests yet

ACT:
  Partially successful:
    ✓ Keep existing tests (prevented 4 bugs)
    ✓ Fix flaky tests
  
  Adjust for CYCLE 2:
    - Expand test coverage to all user flows
    - Add tests for bug-prone areas
    → Start CYCLE 2


CYCLE 2
───────
PLAN:
  Problem: Still 6 bugs/month, need <4
  Current State: 3 critical paths tested, 12 paths total
  Root Cause: UI interaction bugs not covered by integration tests
  Hypothesis: E2E tests for all user flows will reach <4 bugs
  Change: Add E2E tests for remaining 9 flows
  Success Criteria: <4 bugs per month, 80% coverage

DO:
  Week 1-3: Added E2E tests for all user flows
  Week 4: Set up visual regression testing
  Coverage: 12/12 user flows (was 3/12)

CHECK:
  Results after 1 month:
    - Production bugs: 3 ✓ (was 6)
    - Bugs caught in CI: 8 (was 4)
    - Test maintenance time: 3 hours/week
  Analysis: Target achieved! 62% reduction from baseline

ACT:
  Standardize:
    ✓ Made tests required for all PRs
    ✓ Added test checklist to PR template
    ✓ Scheduled weekly test review
    ✓ Created runbook for test maintenance
  
  Monitor: Track bug rate and test effectiveness monthly
  ✓ PDCA complete
```

### Example 3: Improving Code Review Speed

```
PLAN:
  Problem: PRs take 3 days average to merge
  Current State: Manual review, no automation
  Root Cause: Reviewers wait to see if CI passes before reviewing
  Hypothesis: Auto-review + faster CI will reduce to <1 day
  Change: Add automated checks + split long CI jobs
  Success Criteria: Average time to merge <1 day (8 hours)

DO:
  - Set up automated linter checks (fail fast)
  - Split test suite into parallel jobs
  - Added PR template with self-review checklist
  - CI time: 45min → 15min
  - Tracked PR merge time for 2 weeks

CHECK:
  Results:
    - Average time to merge: 1.5 days (was 3)
    - Time waiting for CI: 15min (was 45min)
    - Time waiting for review: 1.3 days (was 2+ days)
  Analysis: CI faster, but review still bottleneck

ACT:
  Partially successful:
    ✓ Keep fast CI improvements
  
  Insight: Real bottleneck is reviewer availability, not CI
  Adjust for new PDCA:
    - Focus on reviewer availability/notification
    - Consider rotating review assignments
  → Start new PDCA cycle with different hypothesis
```

## Notes

- Start with small, measurable changes (not big overhauls)
- PDCA is iterative—multiple cycles normal
- Failed experiments are learning opportunities
- Document everything: easier to see patterns across cycles
- Success criteria must be measurable (not subjective)
- Phase 4 "Act" determines next cycle or completion
- If stuck after 3 cycles, revisit root cause analysis
- PDCA works for technical and process improvements
- Use `/analyse-problem` (A3) for comprehensive documentation
