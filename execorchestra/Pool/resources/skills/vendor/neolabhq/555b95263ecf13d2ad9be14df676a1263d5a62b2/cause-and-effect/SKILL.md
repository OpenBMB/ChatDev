---
name: cause-and-effect
description: Systematic Fishbone analysis exploring problem causes across six categories
argument-hint: Optional problem description to analyze
---

# Cause and Effect Analysis

Apply Fishbone (Ishikawa) diagram analysis to systematically explore all potential causes of a problem across multiple categories.

## Description
Systematically examine potential causes across six categories: People, Process, Technology, Environment, Methods, and Materials. Creates structured "fishbone" view identifying contributing factors.

## Usage
`/cause-and-effect [problem_description]`

## Variables
- PROBLEM: Issue to analyze (default: prompt for input)
- CATEGORIES: Categories to explore (default: all six)

## Steps
1. State the problem clearly (the "head" of the fish)
2. For each category, brainstorm potential causes:
   - **People**: Skills, training, communication, team dynamics
   - **Process**: Workflows, procedures, standards, reviews
   - **Technology**: Tools, infrastructure, dependencies, configuration
   - **Environment**: Workspace, deployment targets, external factors
   - **Methods**: Approaches, patterns, architectures, practices
   - **Materials**: Data, dependencies, third-party services, resources
3. For each potential cause, ask "why" to dig deeper
4. Identify which causes are contributing vs. root causes
5. Prioritize causes by impact and likelihood
6. Propose solutions for highest-priority causes

## Examples

### Example 1: API Response Latency

```
Problem: API responses take 3+ seconds (target: <500ms)

PEOPLE
├─ Team unfamiliar with performance optimization
├─ No one owns performance monitoring
└─ Frontend team doesn't understand backend constraints

PROCESS
├─ No performance testing in CI/CD
├─ No SLA defined for response times
└─ Performance regression not caught in code review

TECHNOLOGY
├─ Database queries not optimized
│  └─ Why: No query analysis tools in place
├─ N+1 queries in ORM
│  └─ Why: Eager loading not configured
├─ No caching layer
│  └─ Why: Redis not in tech stack
└─ Synchronous external API calls
   └─ Why: No async architecture in place

ENVIRONMENT
├─ Production uses smaller database instance than needed
├─ No CDN for static assets
└─ Single region deployment (high latency for distant users)

METHODS
├─ REST API design requires multiple round trips
├─ No pagination on large datasets
└─ Full object serialization instead of selective fields

MATERIALS
├─ Large JSON payloads (unnecessary data)
├─ Uncompressed responses
└─ Third-party API (payment gateway) is slow
   └─ Why: Free tier with rate limiting

ROOT CAUSES:
- No performance requirements defined (Process)
- Missing performance monitoring tooling (Technology)
- Architecture doesn't support caching/async (Methods)

SOLUTIONS (Priority Order):
1. Add database indexes (quick win, high impact)
2. Implement Redis caching layer (medium effort, high impact)
3. Make external API calls async with webhooks (high effort, high impact)
4. Define and monitor performance SLAs (low effort, prevents regression)
```

### Example 2: Flaky Test Suite

```
Problem: 15% of test runs fail, passing on retry

PEOPLE
├─ Test-writing skills vary across team
├─ New developers copy existing flaky patterns
└─ No one assigned to fix flaky tests

PROCESS
├─ Flaky tests marked as "known issue" and ignored
├─ No policy against merging with flaky tests
└─ Test failures don't block deployments

TECHNOLOGY
├─ Race conditions in async test setup
├─ Tests share global state
├─ Test database not isolated per test
├─ setTimeout used instead of proper waiting
└─ CI environment inconsistent (different CPU/memory)

ENVIRONMENT
├─ CI runner under heavy load
├─ Network timing varies (external API mocks flaky)
└─ Timezone differences between local and CI

METHODS
├─ Integration tests not properly isolated
├─ No retry logic for legitimate timing issues
└─ Tests depend on execution order

MATERIALS
├─ Test data fixtures overlap
├─ Shared test database polluted
└─ Mock data doesn't match production patterns

ROOT CAUSES:
- No test isolation strategy (Methods + Technology)
- Process accepts flaky tests (Process)
- Async timing not handled properly (Technology)

SOLUTIONS:
1. Implement per-test database isolation (high impact)
2. Replace setTimeout with proper async/await patterns (medium impact)
3. Add pre-commit hook blocking flaky test patterns (prevents new issues)
4. Enforce policy: flaky test = block merge (process change)
```

### Example 3: Feature Takes 3 Months Instead of 3 Weeks

```
Problem: Simple CRUD feature took 12 weeks vs. 3 week estimate

PEOPLE
├─ Developer unfamiliar with codebase
├─ Key architect on vacation during critical phase
└─ Designer changed requirements mid-development

PROCESS
├─ Requirements not finalized before starting
├─ No code review for first 6 weeks (large diff)
├─ Multiple rounds of design revision
└─ QA started late (found issues in week 10)

TECHNOLOGY
├─ Codebase has high coupling (change ripple effects)
├─ No automated tests (manual testing slow)
├─ Legacy code required refactoring first
└─ Development environment setup took 2 weeks

ENVIRONMENT
├─ Staging environment broken for 3 weeks
├─ Production data needed for testing (compliance delay)
└─ Dependencies blocked by another team

METHODS
├─ No incremental delivery (big bang approach)
├─ Over-engineering (added future features "while we're at it")
└─ No design doc (discovered issues during implementation)

MATERIALS
├─ Third-party API changed during development
├─ Production data model different than staging
└─ Missing design assets (waited for designer)

ROOT CAUSES:
- No requirements lock-down before start (Process)
- Architecture prevents incremental changes (Technology)
- Big bang approach vs. iterative (Methods)
- Development environment not automated (Technology)

SOLUTIONS:
1. Require design doc + finalized requirements before starting (Process)
2. Implement feature flags for incremental delivery (Methods)
3. Automate dev environment setup (Technology)
4. Refactor high-coupling areas (Technology, long-term)
```

## Notes
- Fishbone reveals systemic issues across domains
- Multiple causes often combine to create problems
- Don't stop at first cause in each category—dig deeper
- Some causes span multiple categories (mark them)
- Root causes usually in Process or Methods (not just Technology)
- Use with `/why` command for deeper analysis of specific causes
- Prioritize solutions by: impact × feasibility ÷ effort
- Address root causes, not just symptoms

