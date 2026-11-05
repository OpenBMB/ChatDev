---
name: design-testing-strategy
description: Use before writing any type of tests. Distills 14 industry sources into deterministic decision gates, schemas, and worked test examples.
---

# Design Testing Strategy

A reference manual for designing a fit-for-purpose, fit-for-criticality testing strategy. 

This skill is **decision-oriented**, not philosophical: every gate is deterministic (ON when X / OFF when Y), every schema is enforced (field ordering matters), every example is worked end-to-end. 

## How To Use This Skill

1. Read **Decision Gates** in order (Gate 0 -> Gate 6). Each gate is independent — you may finish with any subset of test types ON.
2. Apply **Strategic Skip Heuristics** to remove ON gates that would yield low ROI for this artifact.
3. For each ON gate, fill the **Test Matrix Schema** (`selected_types` entry) — the field order is load-bearing.
4. List rejected types in `rejected_types` and deliberate skips in `deliberately_skipped`.
5. Produce a **Test Cases to Cover** markdown bullet list using ISTQB techniques from **Case Design Techniques**.
6. Cross-check against the matching **Worked Example** (A pure function / B HTTP+DB endpoint / C UI component).

---

## Decision Gates

Apply gates in numeric order. Each gate produces an independent boolean (`applies: true|false`). Gates do NOT veto each other — a single artifact may have unit + integration + contract + property-based all ON.

| # | Type | ON when | OFF when | Source |
|---|------|---------|----------|--------|
| 0 | **Skip All** | Criticality is `NONE` (docs-only, comments, formatting, generated code, config without logic, throwaway prototypes) | Anything with branching, computed output, side effects, or user-visible behavior | [Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) — "Test ruthlessly and effectively" implies effective skipping when ROI is zero |
| 1 | **Unit** | Code contains any logic: branches, loops, conditionals, computation, transformation, parsing, validation, formatting | Pure declarative wiring (DI registration, route table) with no behavior | [Test Pyramid (Vocke)](https://martinfowler.com/articles/practical-test-pyramid.html) base layer + [Beck TDD](https://www.oreilly.com/library/view/test-driven-development/0321146530/) Red-Green-Refactor unit |
| 2 | **Integration** | Boundary crossing: HTTP call, DB query, external SDK, message queue, filesystem I/O, OR collaboration with >=2 distinct collaborators where unit doubles distort behavior | Pure function with no I/O and 0-1 stable collaborators | [Testing Trophy (Dodds)](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) — integration is the highest-ROI layer; [Google "Follow the User"](https://testing.googleblog.com/2020/10/testing-on-toilet-testing-ui-logic.html) |
| 3 | **Component or E2E** | UI surface AND criticality >= MEDIUM-HIGH AND user-facing critical path (signup, checkout, auth, payment, primary CTA) | Internal admin-only screens, dev tooling, or non-critical UI | [Test Pyramid top](https://martinfowler.com/articles/practical-test-pyramid.html) + [ISO/IEC/IEEE 29119](https://en.wikipedia.org/wiki/ISO/IEC_29119) risk ranking + [Google e2e principles](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html) |
| 4 | **Contract** | Public API consumed by >=1 distinct clients (mobile + web, multiple internal services, external partners) AND independent deploy cadence | API where consumer and provider deploy together | [Pact / CDC](https://docs.pact.io/) + [Pactflow CDC explainer](https://pactflow.io/what-is-consumer-driven-contract-testing/) |
| 5 | **Smoke** | Deployable surface (web app, API, service) AND a deploy/CI pipeline exists where post-deploy validation is meaningful | Library, internal helper, or no deploy pipeline | [Google "What Makes a Good End-to-End Test"](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html) — smoke = minimal e2e for deploy gate |
| 6 | **Property-Based** | Input domain is large or unbounded (numeric ranges, strings, lists, parsers, serializers, encoders, math) AND invariants are stable (round-trip, idempotency, monotonicity, commutativity) AND criticality >= MEDIUM-HIGH | Small finite input domain, unstable invariants, or LOW criticality | [Hypothesis / QuickCheck](https://hypothesis.works/articles/what-is-property-based-testing/) |

### Gate Application Algorithm

```
for gate in [Gate 0, Gate 1, ..., Gate 6]:
    if gate.ON_condition_met(artifact):
        result[gate.type] = applies: true
    else:
        result[gate.type] = applies: false

if Gate 0 is true:
    short-circuit: emit empty selected_types, document criticality=NONE, stop
```

**Criticality Scale** (used by Gates 3 and 6):

| Level | Definition |
|-------|------------|
| `NONE` | Docs, formatting, generated code, throwaway code, configs without logic |
| `LOW` | Internal dev tooling, admin-only screens, logging formatters |
| `MEDIUM` | Standard CRUD, internal APIs with a single team consumer, non-critical UI, helpers and utilities |
| `MEDIUM-HIGH` | User-facing UI on critical paths, public APIs with multiple consumers, business workflows |
| `HIGH` | Money movement, auth/authz decisions, security-critical validation, data integrity, regulated domains |

---

## Test Type Reference

| Type | Use when | Do NOT use when | Frameworks | Typical dependencies | Google Size |
|------|----------|-----------------|------------|----------------------|-------------|
| **unit** | Pure logic, single function/method/class, deterministic inputs | Code is just I/O orchestration with no logic | vitest, jest, pytest, go test, JUnit, xUnit, RSpec | None (or in-memory fakes) | [Small](https://testing.googleblog.com/2010/12/test-sizes.html) |
| **integration** | Boundary crossing (DB, HTTP, queue, FS); multiple collaborators where mocking distorts behavior | Pure function with no boundary | vitest, jest, pytest, go test, JUnit + [Testcontainers](https://testcontainers.com/), supertest, TestRestTemplate | Real Postgres/Redis/Kafka via Testcontainers, in-process HTTP server, real FS in tmpdir | [Medium](https://testing.googleblog.com/2010/12/test-sizes.html) (single machine, localhost OK) |
| **component** | UI rendering + interaction within a single component, no full app context | Backend-only logic; multi-page user flow | React Testing Library, Vue Test Utils, Angular TestBed, Storybook interaction tests | jsdom or happy-dom, mocked network at fetch/axios level | Small to Medium |
| **e2e** | Full user path through running app: real browser, real backend, real DB | Internal helper, single component, non-critical UI | [Playwright](https://playwright.dev/), [Cypress](https://www.cypress.io/), Selenium | Real running app + Testcontainers-backed DB or seeded staging | [Large](https://abseil.io/resources/swe-book/html/ch11.html) (multi-process, possibly multi-machine) |
| **smoke** | Post-deploy go/no-go: hit / health, key endpoints respond, login works | Detailed correctness; smoke is shallow by design | Playwright (1-3 critical paths), HTTP probe scripts, k6 minimal scenarios | Real deployed environment | Large |
| **contract** | Public API consumed by 2+ distinct clients with independent deploy cadence | Single-consumer internal API; provider and consumer deploy together | [Pact](https://docs.pact.io/), Spring Cloud Contract, OpenAPI schema validators | Pact broker or contract files in repo | Medium |
| **property-based** | Large/unbounded input domain with stable invariants (parser, serializer, encoder, math) | Small finite input space; unstable invariants | [Hypothesis](https://hypothesis.works/) (Python), fast-check (TS), QuickCheck (Haskell), jqwik (Java), proptest (Rust) | Same as unit | Small |

### Google Test Size Mapping

[Google Test Sizes (Bland)](https://mike-bland.com/2011/11/01/small-medium-large.html) and [SWE at Google Ch.11](https://abseil.io/resources/swe-book/html/ch11.html) classify tests by **resources** (size), independent of **scope** (paths covered):

| Size | Process model | Network | Filesystem | Time budget | Notes |
|------|---------------|---------|------------|-------------|-------|
| `small` | Single process, single thread | None | None (in-memory only) | < 100ms | Fast, hermetic, parallelizable |
| `medium` | Single machine, multiple processes allowed | localhost only | tmpdir allowed | < 1s | Testcontainers fits here |
| `large` | Multi-machine | External network allowed | Persistent FS allowed | < 15min | Full e2e |
| `enormous` | Distributed | Wide network | Anywhere | longer | Cluster / chaos |

A test's **type** (unit/integration/e2e) and **size** (small/medium/large) are orthogonal: a small integration test (Testcontainers Postgres in same process via JDBC) is legitimate.

### Playwright vs Cypress (UI e2e)

| Dimension | [Playwright](https://playwright.dev/) | [Cypress](https://www.cypress.io/) |
|-----------|---------------------------------------|-----------------------------------|
| Browsers | Chromium, Firefox, WebKit | Chromium, Firefox, WebKit (limited) |
| Multi-tab / multi-origin | Yes | Limited |
| Parallelism | Built-in shards | Paid dashboard or external |
| Network interception | Robust route-level | cy.intercept |
| Default | Choose Playwright for new projects unless team already standardized on Cypress | Choose Cypress when team has heavy investment |

---

## Case Design Techniques

Use ISTQB Foundation Level black-box techniques to derive **what** to test inside each chosen test type. References: [ISTQB BVA white paper](https://istqb.org/wp-content/uploads/2025/10/Boundary-Value-Analysis-white-paper.pdf), [ASTQB black-box techniques](https://astqb.org/4-2-black-box-test-techniques/).

### 1. Equivalence Partitioning (EP)

Divide input domain into partitions where the system is expected to behave the same way; ONE test per partition is sufficient.

**Worked example** — `discount(orderTotal: number) -> number`:

| Partition | Range | Representative test input | Expected |
|-----------|-------|---------------------------|----------|
| Below threshold | `0 <= total < 100` | `50` | `0% discount` |
| Mid tier | `100 <= total < 500` | `250` | `5% discount` |
| Top tier | `total >= 500` | `1000` | `10% discount` |
| Invalid (negative) | `total < 0` | `-1` | `throw / error` |

Four tests cover all partitions. EP alone misses boundaries — combine with BVA.

### 2. Boundary Value Analysis (BVA)

Bugs cluster at boundaries. For every boundary value `B`, test **`B-1`, `B`, `B+1`** (or for floats, the smallest representable step).

**Worked example** — same `discount` function, boundary at `100`:

| Test input | Why | Expected |
|------------|-----|----------|
| `99` (= B-1) | Last value of "below threshold" partition | `0% discount` |
| `100` (= B) | First value of "mid tier" partition | `5% discount` |
| `101` (= B+1) | Confirms not off-by-two | `5% discount` |

Repeat for boundary at `500`: test `499`, `500`, `501`. Total: 6 boundary tests + 4 EP tests = 10 cases.

The `B-1 / B / B+1` triplet has the same shape across boundaries (vary input, vary expected output, identical assertion); this is a natural fit for a **table-driven test** (see sub-section 5 below).

### 3. Decision Tables

When output depends on combinations of conditions. Each column is a rule.

**Worked example** — `canCheckout(cartHasItems, paymentValid, addressOnFile)`:

| Condition / Rule | R1 | R2 | R3 | R4 |
|------------------|----|----|----|----|
| cartHasItems | T | T | T | F |
| paymentValid | T | T | F | * |
| addressOnFile | T | F | * | * |
| **Result** | allow | block:address | block:payment | block:cart |

Four tests, one per rule (`*` = don't care, dropped via merging).

### 4. State Transition

When behavior depends on history. Identify states, events, and forbidden transitions.

**Worked example** — Order state machine with states `{draft, submitted, paid, shipped, cancelled}`:

| From | Event | To | Test |
|------|-------|----|----|
| draft | submit | submitted | happy path |
| submitted | pay | paid | happy path |
| paid | ship | shipped | happy path |
| draft | cancel | cancelled | early cancel |
| paid | cancel | reject | forbidden — refund flow required, NOT direct cancel |
| shipped | submit | reject | forbidden |

Cover one test per legal transition + one per forbidden transition (negative path).

### 5. Table-Driven Tests

When EP, BVA, or decision-table analysis yields **3+ cases with the same shape** (same setup, same assertion, only inputs and expected outputs differ — e.g., parsing valid/invalid date formats; computing tax across brackets; routing rules) collapse them into a single **table-driven test**. The cases become rows in a data table; the test body iterates the rows and runs one assertion per row. References: Dave Cheney, [Prefer table-driven tests](https://dave.cheney.net/2019/05/07/prefer-table-driven-tests); [Go wiki: TableDrivenTests](https://go.dev/wiki/TableDrivenTests).

Do **NOT** force a table when setup, framework calls, or the assertion shape varies substantially across cases. Forced uniformity hides real differences behind a single name and produces obscure failure messages — keep those as separate, individually named tests.

**Worked example** — six EP+BVA cases for `discount(orderTotal)` (boundary at `100`) collapsed into one table-driven unit test (TS / vitest syntax; the same pattern applies to Go `t.Run`, JUnit `@ParameterizedTest`, pytest `parametrize`):

```ts
describe("discount", () => {
  const cases: Array<{ name: string; input: number; expected: number }> = [
    { name: "EP: below threshold (typical)", input: 50,  expected: 0    },
    { name: "BVA: B-1 at boundary 100",      input: 99,  expected: 0    },
    { name: "BVA: B at boundary 100",        input: 100, expected: 0.05 },
    { name: "BVA: B+1 at boundary 100",      input: 101, expected: 0.05 },
    { name: "EP: mid tier (typical)",        input: 250, expected: 0.05 },
    { name: "EP: top tier (typical)",        input: 1000, expected: 0.10 },
  ];

  for (const c of cases) {
    it(c.name, () => {
      expect(discount(c.input)).toBe(c.expected);
    });
  }
});
```

The `name` column is mandatory: each row must produce an individually addressable test so failures point to the specific case, not "row 3 of 6". Rows that need a different assertion (e.g., the negative-input case throws) stay as separate tests outside the table.

---

## Dependency Decision

For Gate 2 (Integration) and Gate 3 (Component/E2E), choose dependencies deliberately. The goal is **maximum realism that still runs deterministically in CI**.

| Dependency style | Use when | Avoid when | Notes |
|------------------|----------|------------|-------|
| **Real infra via [Testcontainers](https://testcontainers.com/)** | DB/Redis/Kafka/Browser, dev needs real driver behavior, hermetic CI required | Cold-start budget < 1s, no Docker available | Default for integration tests on Postgres / Redis / Kafka / Localstack |
| **In-memory fake** | Owned interface, semantics are simple (key-value, list), test speed critical | Fake diverges from real — silent bugs at integration boundary | Acceptable for repository ports in hexagonal architectures, IF the port has its own contract test against real infra |
| **Mock (test double)** | Single collaborator with pure interface; test focuses on protocol (was X called with Y) | You're mocking >2 collaborators or mocking data structures (anti-pattern: incomplete mocks) | Mocks are tools to isolate, not things to test |
| **Stubbed HTTP** | Calling external SaaS where Testcontainers / Localstack option doesn't exist | When Pact / CDC is needed (use contract tests instead) | nock (Node), responses (Python), WireMock (JVM) |
| **Real external service** | Smoke test in staging only | Unit / integration / CI — always non-deterministic | Reserve for smoke tests against staging |

**Tradeoff summary**: Testcontainers > in-memory fake > mock, but cost goes the same direction. Pick the cheapest level that doesn't lie about the boundary's behavior.

---

## Strategic Skip Heuristics

Explicit "don't bother" rules. Skipping these is not laziness — it is risk-adjusted ROI per [ISO/IEC/IEEE 29119 risk-based testing](https://en.wikipedia.org/wiki/ISO/IEC_29119) and [Risk-Based Testing](https://www.softwaretestinghelp.com/risk-management-during-test-planning-risk-based-testing/).

| Skip | Rule |
|------|------|
| **No e2e for internal helpers** | If artifact has no UI surface and no user-facing path, skip e2e. Unit + integration is sufficient. |
| **No contract test for bound by deploy consumer API** | If only one client consumes the API and they deploy together, contract testing adds maintenance with no decoupling benefit. |
| **No property-based on small finite domains** | If input space is `enum {A, B, C}`, EP + BVA already covers it; property-based adds infra without finding more bugs. |
| **No integration test for pure functions** | Adding a Postgres container to test a `formatCurrency` helper is waste. Unit only. |
| **No component test for static markup** | If the component has no state, no events, no conditional rendering, a snapshot is enough — or skip entirely. |
| **No unit test for declarative wiring** | DI bindings, route registration, schema declarations: assert at integration level (does the route serve the right handler) instead. |
| **No e2e for things integration covers reliably** | Per [Google e2e principles](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html): the smaller the test you can use to cover a behavior, the better. e2e is the exception, not the default. |
| **No tests for spike/throwaway code** | Per [Beck TDD](https://www.oreilly.com/library/view/test-driven-development/0321146530/): if the artifact will be deleted within hours, document the exception with the human partner. Then write tests on the kept version. |
| **No "and" tests** | If a test name contains "and", split it into separate tests (one assertion per behavior). |

---

## Test Matrix Schema

Every test strategy MUST be expressed as the YAML block below. **Field ordering inside each list entry is load-bearing** — judges and downstream tools parse the first key as the critical one (rationale / reason / why), and the second key as the categorical one (type / what).

### Schema

```yaml
test_strategy:
  artifact: "<path or short identifier>"
  rationale: "Why this test strategy is being applied to this artifact (specific, evidence-based)"
  criticality: "NONE | LOW | MEDIUM | MEDIUM-HIGH | HIGH"

  selected_types:
    - rationale: "Why this type is being applied to this artifact (specific, evidence-based)"
      type: "unit | integration | component | e2e | smoke | contract | property-based"
      size: "small | medium | large | enormous"
      framework: "vitest | jest | pytest | go test | JUnit | playwright | cypress | pact | hypothesis | ..."
      dependencies:
        - "List of dependencies: real Postgres via Testcontainers, in-memory fake, mocked HTTP via nock, etc."
      gate: "Gate N (the gate that triggered this selection)"

  rejected_types:
    - reason: "Why this type does NOT apply to this artifact (cite Strategic Skip Heuristic or gate that did not trigger)"
      type: "unit | integration | component | e2e | smoke | contract | property-based"

  deliberately_skipped:
    - why: "Cost / risk justification for skipping despite a partial signal"
      what: "A specific category of test cases being skipped (e.g., 'browser compatibility on IE11', 'load testing beyond 100 RPS')"
```

### Worked YAML Example

```yaml
test_strategy:
  artifact: "POST /users (user registration endpoint)"
  rationale: "User registration is a critical user-facing path; can be used by web and mobile apps independently of each other."
  criticality: "MEDIUM-HIGH"

  selected_types:
    - rationale: "Endpoint contains validation logic (email format, password rules, uniqueness) — Gate 1 ON for branch coverage"
      type: "unit"
      size: "small"
      framework: "vitest"
      dependencies: ["in-memory user repository fake"]
      gate: "Gate 1"
    - rationale: "Endpoint writes to Postgres and emits user.created event to Kafka — Gate 2 ON, real boundary behavior matters"
      type: "integration"
      size: "medium"
      framework: "vitest + supertest + Testcontainers"
      dependencies: ["Postgres 15 via Testcontainers", "Kafka via Testcontainers"]
      gate: "Gate 2"
    - rationale: "Consumed by mobile app and web app on independent deploy cadences — Gate 4 ON, prevents drift"
      type: "contract"
      size: "medium"
      framework: "Pact"
      dependencies: ["Pact broker"]
      gate: "Gate 4"

  rejected_types:
    - reason: "No UI surface in this artifact — Gate 3 OFF"
      type: "component"
    - reason: "No UI surface — Gate 3 OFF; e2e covered by web/mobile apps separately"
      type: "e2e"
    - reason: "Input domain (email, password) is large but invariants are well-covered by EP+BVA at unit level — property-based ROI is low at MEDIUM-HIGH criticality, only triggers Gate 6 partially"
      type: "property-based"

  deliberately_skipped:
    - why: "Project does not have post-deploy probe pipeline yet; smoke would be no-op"
      what: "Smoke test for /users after deploy"
    - why: "Non-functional load testing is out of scope for this task; tracked separately in performance backlog"
      what: "Load test verifying p99 < 200ms at 1000 RPS"
```

**Field ordering checklist** (judges check this verbatim):

- `test_strategy`: `artifact` BEFORE `rationale` BEFORE `criticality`.
- `selected_types[*]`: `rationale` BEFORE `type` BEFORE `size` BEFORE `framework` BEFORE `dependencies` BEFORE `gate`.
- `rejected_types[*]`: `reason` BEFORE `type`.
- `deliberately_skipped[*]`: `why` BEFORE `what`.

---

## Case Listing Schema

After the matrix, produce a flat markdown bullet list of test cases to be implemented. This is separate from the YAML matrix because:
- a. it lists *what* to test, not *how*
- b. it links back to acceptance criteria

### Format

```markdown
## Test Cases to Cover

### AC-N: [criterion title]
- [type] description 
- [type] description 

### AC-N: [criterion title]
- [type] description 
- [type] description 
```

Where:

- `type` matches one of `selected_types[*].type` from the matrix
- `description` follows AAA / [Given-When-Then (Dan North BDD)](https://dannorth.net/introducing-bdd/) shape — see [Bill Wake AAA (2001)](https://xp123.com/articles/3a-arrange-act-assert/)
- `AC-N` references the acceptance criterion the case verifies (omit if non-AC-bound, e.g., infrastructure smoke)

### Worked Example

```markdown
## Test Cases to Cover

### AC-1: Discount returns the correct percentage based on the total
- [unit] discount returns 0% when total = 0 [EP partition: below threshold]
- [unit] discount returns 0% when total = 99 [BVA: B-1 at boundary 100]
- [unit] discount returns 5% when total = 100 [BVA: B at boundary 100]
- [unit] discount returns 5% when total = 101 [BVA: B+1 at boundary 100]

### AC-2: Discount fails when total is invalid
- [unit] discount throws when total = -1 [EP partition: invalid]

### AC-3: /orders saves the order to the database
- [integration] POST /orders persists order to Postgres and returns 201 with order id

### AC-4: /orders rejects duplicate idempotency key
- [integration] POST /orders rejects duplicate idempotency key with 409

### AC-5: /orders/:id returns order by id
- [contract] GET /orders/:id returns schema matching mobile-app pact
```

---

## Sources & Further Reading

These 14 sources back every gate and rule above. When in doubt, consult the source linked at that gate.

1. **Test Pyramid** — Mike Cohn (2009, *Succeeding with Agile*) + Ham Vocke, [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html), martinfowler.com.
2. **Testing Trophy** — Kent C. Dodds (2018), [The Testing Trophy and Testing Classifications](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) and [Write Tests](https://kentcdodds.com/blog/write-tests).
3. **Google Test Sizes** — Mike Bland (2011), [Small / Medium / Large](https://mike-bland.com/2011/11/01/small-medium-large.html); [Software Engineering at Google Ch.11](https://abseil.io/resources/swe-book/html/ch11.html); [Test Sizes (Google Testing Blog)](https://testing.googleblog.com/2010/12/test-sizes.html).
4. **Google Testing on the Toilet** — [What Makes a Good End-to-End Test](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html), [Testing UI Logic - Follow the User](https://testing.googleblog.com/2020/10/testing-on-toilet-testing-ui-logic.html), [Origins (Mike Bland)](https://mike-bland.com/2011/10/25/testing-on-the-toilet.html).
5. **ISTQB Foundation Level** — Black-box techniques: [Boundary Value Analysis white paper](https://istqb.org/wp-content/uploads/2025/10/Boundary-Value-Analysis-white-paper.pdf); [ASTQB Black-Box Techniques](https://astqb.org/4-2-black-box-test-techniques/).
6. **ISO/IEC/IEEE 29119** — Risk-based test process standard. [Wikipedia overview](https://en.wikipedia.org/wiki/ISO/IEC_29119).
7. **Kent Beck — *Test Driven Development: By Example*** (Addison-Wesley, 2002). [Publisher page](https://www.oreilly.com/library/view/test-driven-development/0321146530/). ISBN 978-0321146533.
8. **The Pragmatic Programmer (20th Anniversary Edition)** — Hunt & Thomas (2019). [pragprog.com](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/).
9. **AAA pattern** — Bill Wake (2001), [3A — Arrange, Act, Assert](https://xp123.com/articles/3a-arrange-act-assert/). **Given-When-Then** — Dan North, [Introducing BDD](https://dannorth.net/introducing-bdd/).
10. **Property-based testing** — [Hypothesis: What is property-based testing?](https://hypothesis.works/articles/what-is-property-based-testing/); QuickCheck (Haskell), fast-check (TS).
11. **Contract testing / Consumer-Driven Contracts** — [Pact docs](https://docs.pact.io/); [Pactflow CDC explainer](https://pactflow.io/what-is-consumer-driven-contract-testing/).
12. **Testcontainers** — [testcontainers.com](https://testcontainers.com/).
13. **Table-driven tests** — Dave Cheney, [Prefer table-driven tests](https://dave.cheney.net/2019/05/07/prefer-table-driven-tests); [Go wiki: TableDrivenTests](https://go.dev/wiki/TableDrivenTests).
14. **Risk-based testing** — [Risk Management During Test Planning (softwaretestinghelp.com)](https://www.softwaretestinghelp.com/risk-management-during-test-planning-risk-based-testing/).

---

## Worked Examples

Each example shows: 
- a. the artifact and acceptance criteria
- b. gate-by-gate walkthrough
- c. `test_strategy` YAML following the schema
- d. `Test Cases to Cover` list
- e. commentary on rejected types

---

### Example A — Pure Helper Function: `formatCurrency(amount: number, code: string): string`

**Artifact**

```ts
function formatCurrency(amount: number, code: string): string;
// e.g. formatCurrency(1234.5, "USD") -> "$1,234.50"
//      formatCurrency(1234.5, "EUR") -> "€1.234,50"
```

**Acceptance criteria**:

- AC-1: USD output uses `$` prefix, comma thousands, period decimal, two decimal places.
- AC-2: EUR output uses `€` prefix, period thousands, comma decimal, two decimal places.
- AC-3: Throws `Error("Unknown currency code")` for unsupported codes.
- AC-4: `amount = 0` formats as `"$0.00"` / `"€0,00"`.

**Criticality**: `LOW` (helper used in display only, no money movement here).

**Gate Walkthrough**

| Gate | Decision | Reason |
|------|----------|--------|
| 0 Skip | OFF | Has logic |
| 1 Unit | **ON** | Pure logic with branches per currency code — [Test Pyramid base](https://martinfowler.com/articles/practical-test-pyramid.html) |
| 2 Integration | OFF | No I/O, no boundary — [Skip Heuristic: no integration for pure functions](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) |
| 3 Component/E2E | OFF | No UI surface |
| 4 Contract | OFF | Not a public API |
| 5 Smoke | OFF | Not deployable |
| 6 Property-Based | **ON** (partial) | Numeric input is unbounded, but invariants exist (round-trip via parse, monotonicity in amount) — [Hypothesis](https://hypothesis.works/articles/what-is-property-based-testing/). Promote at MEDIUM-HIGH; here LOW criticality means we apply it sparingly (1-2 properties) |

**`test_strategy` YAML**

```yaml
test_strategy:
  artifact: "src/util/formatCurrency.ts"
  rationale: "Pure helper function used in display only; no money movement here."
  criticality: "LOW"

  selected_types:
    - rationale: "Pure logic with currency-specific branches and number formatting; EP+BVA on amount, decision table on currency code"
      type: "unit"
      size: "small"
      framework: "vitest"
      dependencies: []
      gate: "Gate 1"
    - rationale: "Amount domain is unbounded floats; invariant 'parseCurrency(formatCurrency(x, c)) ~= x' is stable; sparingly applied (1-2 properties) at LOW criticality"
      type: "property-based"
      size: "small"
      framework: "fast-check"
      dependencies: []
      gate: "Gate 6"

  rejected_types:
    - reason: "No I/O, no boundary, no collaborators - Gate 2 OFF"
      type: "integration"
    - reason: "No UI surface - Gate 3 OFF"
      type: "component"
    - reason: "No UI surface - Gate 3 OFF"
      type: "e2e"
    - reason: "Internal helper, not consumed across deploys - Gate 4 OFF"
      type: "contract"
    - reason: "Library helper, no deploy pipeline target - Gate 5 OFF"
      type: "smoke"

  deliberately_skipped:
    - why: "Locale list is finite (USD, EUR); exhaustive enumeration via decision table is sufficient and more maintainable than i18n property tests"
      what: "Property-based fuzzing of currency code beyond known list"
```

**Test Cases to Cover**

```markdown
### AC-1: USD output uses `$` prefix, comma thousands, period decimal, two decimal places.
- [unit] formatCurrency(1234.5, "USD") returns "$1,234.50" [EP: typical USD]
- [unit] formatCurrency(0.01, "USD") returns "$0.01" [BVA: B+1 smallest non-zero]
- [unit] formatCurrency(-0.01, "USD") returns "-$0.01" [BVA: B-1 negative side]

### AC-2: EUR output uses `€` prefix, period thousands, comma decimal, two decimal places.
- [unit] formatCurrency(1234.5, "EUR") returns "€1.234,50" [EP: typical EUR]
- [property-based] for any non-NaN finite x in [-1e9, 1e9] and code in {USD, EUR}: parseCurrency(formatCurrency(x, code)) is within 0.005 of x [round-trip invariant]

### AC-3: Throws `Error("Unknown currency code")` for unsupported codes.
- [unit] formatCurrency(1, "XYZ") throws Error("Unknown currency code") [Decision table: unknown code]

### AC-4: `amount = 0` formats as `"$0.00"` / `"€0,00"`.
- [unit] formatCurrency(0, "USD") returns "$0.00" [BVA: B at amount=0]
- [unit] formatCurrency(0, "EUR") returns "€0,00" [BVA: B at amount=0 for EUR]

```

**Why types were rejected**: Helper has no boundaries (no integration), no UI (no component/e2e), is internal and library-style (no contract/smoke), and at LOW criticality the cost of additional test types far exceeds the benefit.

---

### Example B — HTTP POST Endpoint with DB and Multi-Consumer: `POST /users`

**Artifact**

A user-registration endpoint that:

1. Validates request body (email format, password complexity, age >= 13).
2. Checks email uniqueness against Postgres.
3. Inserts user record (transactional).
4. Emits `user.created` event to Kafka.
5. Returns `201` with `{id, email, createdAt}`.
6. Returns `400` for invalid input, `409` for duplicate email.

**Consumed by**: mobile app (iOS/Android) and web app on independent deploy cadences.

**Acceptance criteria**:

- AC-1: Valid request returns `201` and persists user.
- AC-2: Invalid email format returns `400` with field-level error.
- AC-3: Password not meeting policy returns `400`.
- AC-4: Duplicate email returns `409`.
- AC-5: Successful registration emits exactly one `user.created` event.
- AC-6: Response schema is stable for mobile + web consumers.

**Criticality**: `MEDIUM-HIGH` (auth surface, identity domain, multi-consumer public API).

**Gate Walkthrough**

| Gate | Decision | Reason |
|------|----------|--------|
| 0 Skip | OFF | Has substantial logic |
| 1 Unit | **ON** | Validators (email, password, age) are pure logic — [Test Pyramid base](https://martinfowler.com/articles/practical-test-pyramid.html) |
| 2 Integration | **ON** | Boundary crossing: HTTP, Postgres, Kafka — [Testing Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) ROI sweet spot |
| 3 Component/E2E | OFF (here) | No UI in this artifact; UI lives in mobile + web repos and tests itself |
| 4 Contract | **ON** | Two distinct consumers (mobile + web) on independent deploy cadences — [Pact CDC](https://pactflow.io/what-is-consumer-driven-contract-testing/) |
| 5 Smoke | **ON** | Deployable HTTP service; post-deploy probe of `/users` registration is meaningful — [Google e2e](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html) |
| 6 Property-Based | OFF | Input domain (email, password, age) is constrained and well-covered by EP+BVA at unit; criticality is MEDIUM-HIGH but Gate 6 OFF on bounded inputs — [Skip Heuristic](https://hypothesis.works/articles/what-is-property-based-testing/) |

**`test_strategy` YAML**

```yaml
test_strategy:
  artifact: "POST /users (user registration endpoint)"
  rationale: "User registration is a critical user-facing path; can be used by web and mobile apps independently of each other."
  criticality: "MEDIUM-HIGH"

  selected_types:
    - rationale: "Validators (email, password, age) are pure logic; EP+BVA on each field; one test per partition"
      type: "unit"
      size: "small"
      framework: "vitest"
      dependencies: ["in-memory user repository fake (for service-level unit if needed)"]
      gate: "Gate 1"
    - rationale: "Endpoint writes to Postgres and emits to Kafka; mocking these distorts transactional and ordering behavior - Testcontainers gives real boundary fidelity"
      type: "integration"
      size: "medium"
      framework: "vitest + supertest + Testcontainers"
      dependencies: ["Postgres 15 via Testcontainers", "Kafka via Testcontainers"]
      gate: "Gate 2"
    - rationale: "Public API consumed by mobile + web on independent deploy cadences; contract testing prevents schema drift breaking either consumer"
      type: "contract"
      size: "medium"
      framework: "Pact (provider verification)"
      dependencies: ["Pact broker", "consumer-published pacts from mobile and web"]
      gate: "Gate 4"
    - rationale: "Deployable HTTP service with a post-deploy pipeline; one minimal smoke verifies /users responds 201 in the deployed environment"
      type: "smoke"
      size: "large"
      framework: "Playwright (1 critical path)"
      dependencies: ["deployed environment URL", "test account seeding"]
      gate: "Gate 5"

  rejected_types:
    - reason: "No UI surface in this artifact - Gate 3 OFF; mobile and web repos own their own component tests"
      type: "component"
    - reason: "No UI surface - Gate 3 OFF; consumer e2e lives in mobile/web repos"
      type: "e2e"
    - reason: "Input domain is bounded and EP+BVA at unit level covers it; property-based on this glue endpoint adds infra without finding more bugs - Gate 6 OFF"
      type: "property-based"

  deliberately_skipped:
    - why: "Performance/load testing is out of scope here; tracked in dedicated performance backlog"
      what: "Load test verifying p99 < 200ms at 1000 RPS"
    - why: "Cross-region failover is owned by infrastructure team, not this endpoint"
      what: "Multi-region availability test"
```

**Test Cases to Cover**

```markdown
### AC-1: Valid request returns `201` and persists user.
- [unit] validateEmail accepts "alice@example.com" [EP: well-formed]
- [integration] POST /users with valid body returns 201 and persists row in Postgres
- [smoke] POST /users in deployed environment returns 201 for a synthetic test account

### AC-2: Invalid email format returns `400` with field-level error.
- [unit] validateEmail rejects "alice@" [EP: missing domain]
- [unit] validateEmail rejects "" [BVA: empty boundary]
- [integration] POST /users with invalid email returns 400 and does NOT persist

### AC-3: Password not meeting policy returns `400`.
- [unit] validatePassword rejects 7-char password [BVA: B-1 at min length 8]
- [unit] validatePassword accepts 8-char password meeting policy [BVA: B at min length]
- [unit] validatePassword accepts 9-char password [BVA: B+1]
- [unit] validateAge rejects 12 [BVA: B-1 at boundary 13]
- [unit] validateAge accepts 13 [BVA: B at boundary 13]

### AC-4: Duplicate email returns `409`.
- [integration] POST /users with duplicate email returns 409 and does NOT emit event

### AC-5: Successful registration emits exactly one `user.created` event.
- [integration] POST /users emits exactly one user.created event to Kafka on success
- [integration] POST /users transaction rolls back when Kafka publish fails [State Transition: failure path]

### AC-6: Response schema is stable for mobile + web consumers.
- [contract] Provider satisfies mobile pact: POST /users response shape matches mobile contract
- [contract] Provider satisfies web pact: POST /users response shape matches web contract
```

**Why types were rejected**: No UI surface (component/e2e belong to consumer apps), bounded input space (property-based ROI low), out-of-scope concerns (load, multi-region) deliberately skipped with rationale.

---

### Example C — UI Form Component: `<RegistrationForm />` (web)

**Artifact**

A React form component:

1. Fields: email, password, confirmPassword, age.
2. Client-side validation: email format, password >= 8 chars with mixed case + digit, passwords match, age >= 13.
3. Submits to `POST /users`.
4. Shows inline field errors and submit-level errors (network, 409 duplicate).
5. Disables submit button while pending; re-enables on response.
6. WCAG 2.1 AA: labels bound to inputs, errors announced via `aria-live`, focus moves to first error on validation failure.

**Acceptance criteria**:

- AC-1: User can submit a valid form and is navigated to `/welcome`.
- AC-2: Invalid email shows inline `"Enter a valid email"`.
- AC-3: Mismatched passwords show inline `"Passwords must match"`.
- AC-4: Submit is disabled while request is in flight.
- AC-5: 409 response from server shows `"This email is already registered"` at form level.
- AC-6: Form is keyboard navigable; focus moves to first error on validation failure.
- AC-7: All inputs have programmatic labels; errors are announced via `aria-live="polite"`.

**Criticality**: `MEDIUM-HIGH` (registration is a critical user-facing path; accessibility is regulated in many jurisdictions).

**Gate Walkthrough**

| Gate | Decision | Reason |
|------|----------|--------|
| 0 Skip | OFF | Behavior + accessibility logic |
| 1 Unit | **ON** | Validation helpers (`validateEmail`, `passwordsMatch`, `parseAge`) are pure logic |
| 2 Integration | OFF (here) | The component itself does not cross a real boundary; network is mocked at fetch level. Network integration is owned by `POST /users` (Example B) |
| 3 Component/E2E | **ON** (component) + **ON** (e2e for the registration path) | UI surface, criticality MEDIUM-HIGH, user-facing critical path — [Test Pyramid top](https://martinfowler.com/articles/practical-test-pyramid.html) + [Follow the User](https://testing.googleblog.com/2020/10/testing-on-toilet-testing-ui-logic.html) |
| 4 Contract | OFF | UI consumes API; provider-side contract tests live in Example B |
| 5 Smoke | **ON** | Web app is deployed; smoke for "registration page renders and submits" is meaningful |
| 6 Property-Based | OFF | Bounded form inputs; EP+BVA covers them |

**`test_strategy` YAML**

```yaml
test_strategy:
  artifact: "src/components/RegistrationForm.tsx"
  rationale: "React form component used in web app; registration is a business-critical user-facing path."
  criticality: "MEDIUM-HIGH"

  selected_types:
    - rationale: "Validation helpers (validateEmail, passwordsMatch, parseAge) are pure logic; EP+BVA per field"
      type: "unit"
      size: "small"
      framework: "vitest"
      dependencies: []
      gate: "Gate 1"
    - rationale: "UI rendering + interaction within a single component; network mocked at fetch level - tests focus on user-facing behavior per Follow the User"
      type: "component"
      size: "small"
      framework: "vitest + React Testing Library"
      dependencies: ["happy-dom", "msw (mock service worker) for fetch"]
      gate: "Gate 3"
    - rationale: "Registration is a critical user-facing path; one e2e covers the full happy path with real backend (Testcontainers-backed)"
      type: "e2e"
      size: "large"
      framework: "Playwright"
      dependencies: ["app server running locally", "Postgres via Testcontainers", "Kafka via Testcontainers"]
      gate: "Gate 3"
    - rationale: "Web app deploys to staging/prod; smoke verifies /register page loads and form submits in deployed env"
      type: "smoke"
      size: "large"
      framework: "Playwright (1 critical path)"
      dependencies: ["deployed environment URL", "test account seeding"]
      gate: "Gate 5"

  rejected_types:
    - reason: "Component does not own a real boundary; network integration is owned by POST /users (provider) - Gate 2 OFF for this artifact"
      type: "integration"
    - reason: "UI consumes the API; provider contract tests live with the provider (POST /users) - Gate 4 OFF for the consumer"
      type: "contract"
    - reason: "Bounded input space; EP+BVA at unit level is sufficient - Gate 6 OFF"
      type: "property-based"

  deliberately_skipped:
    - why: "Cross-browser e2e on legacy browsers (IE11) is out of support per project browser matrix"
      what: "Browser compatibility e2e on IE11 / Edge Legacy"
    - why: "Visual regression (pixel diff) is owned by a separate Storybook chromatic pipeline"
      what: "Pixel-level visual regression assertions"
```

**Test Cases to Cover**

```markdown
### AC-1: User can submit a valid form and is navigated to `/welcome`.
- [unit] validateEmail accepts "alice@example.com" [EP: well-formed]
- [unit] parseAge rejects 12 [BVA: B-1 at boundary 13]
- [unit] parseAge accepts 13 [BVA: B at boundary 13]
- [e2e] user fills valid form, submits, and lands on /welcome page
- [smoke] /register page loads and form submits in deployed environment

### AC-2: Invalid email shows inline `"Enter a valid email"`.
- [unit] validateEmail rejects "" [BVA: empty boundary]
- [unit] validateEmail rejects "alice@" [EP: missing domain]
- [component] entering invalid email and blurring shows "Enter a valid email" inline

### AC-3: Mismatched passwords show inline `"Passwords must match"`.
- [unit] passwordsMatch returns true when both equal "Abcd1234"
- [unit] passwordsMatch returns false when one is "" [BVA: empty]
- [component] entering mismatched passwords shows "Passwords must match" inline

### AC-4: Submit is disabled while request is in flight.
- [component] submit is disabled when password and confirmPassword differ
- [component] submit click disables button while request is pending [State Transition: idle -> pending]

### AC-5: 409 response from server shows `"This email is already registered"` at form level.
- [component] 409 response shows form-level "This email is already registered"

### AC-6: Form is keyboard navigable; focus moves to first error on validation failure.
- [component] validation failure moves focus to first error field [a11y]

### AC-7: All inputs have programmatic labels; errors are announced via `aria-live="polite"`.
- [component] form renders email, password, confirmPassword, age, submit [happy path render]
- [component] all inputs have programmatic labels and errors live in aria-live="polite" region [a11y]

```

**Why types were rejected**: This artifact is a UI consumer — its real boundary is the API, which is tested as integration in Example B (provider side). Property-based testing is not justified for bounded UI input handling. Cross-browser legacy and visual-regression are out of scope and explicitly skipped with rationale.

---

## Skill Self-Check

Before declaring a strategy complete, the loading verify:

- [ ] All 7 gates evaluated explicitly (ON/OFF + reason).
- [ ] `selected_types[*]` order is `rationale -> type -> size -> framework -> dependencies -> gate`.
- [ ] `rejected_types[*]` order is `reason -> type`.
- [ ] `deliberately_skipped[*]` order is `why -> what`.
- [ ] Each AC is referenced by at least one test case.
- [ ] BVA cases enumerate `B-1`, `B`, `B+1` for each numeric boundary.
- [ ] Test sizes (small/medium/large) are assigned per [Google Test Sizes](https://abseil.io/resources/swe-book/html/ch11.html).
- [ ] Test names contain no "and" (per [Skip Heuristic](#strategic-skip-heuristics)).
- [ ] At least one [Strategic Skip Heuristic](#strategic-skip-heuristics) was applied or explicitly considered and overridden with rationale.

If any check fails, revise the strategy before delivering.

## Coverage Analysis

Mutation testing and other coverage-analysis methods (used **after** tests are written to assess test-suite quality) are documented in the companion `test-coverage` skill.