## The 9 Categories

### 1. ARITHMETIC
**Focus**: Overflow protection, precision handling, formula specification, edge case testing

**I'll analyze**:
- Overflow protection mechanisms (Solidity 0.8, SafeMath, checked_*, saturating_*)
- Unchecked arithmetic blocks and documentation
- Division/rounding operations
- Arithmetic in critical functions (balances, rewards, fees)
- Test coverage for arithmetic edge cases
- Arithmetic specification documents

**WEAK if**:
- No overflow protection without justification
- Unchecked arithmetic not documented
- No arithmetic specification OR spec doesn't match code
- No testing strategy for arithmetic
- Critical edge cases not tested

**MODERATE requires**:
- All weak criteria resolved
- Unchecked arithmetic minimal, justified, documented
- Overflow/underflow risks documented and tested
- Explicit rounding for precision loss
- Automated testing (fuzzing/formal methods)
- Stateless arithmetic functions
- Bounded parameters with explained ranges

**SATISFACTORY requires**:
- All moderate criteria met
- Precision loss analyzed vs ground-truth
- All trapping operations identified
- Arithmetic spec matches code one-to-one
- Automated testing covers all operations in CI

---

### 2. AUDITING
**Focus**: Events, monitoring systems, incident response

**I'll analyze**:
- Event definitions and emission patterns
- Events for critical operations (transfers, access changes, parameter updates)
- Event naming consistency
- Critical functions without events

**I'll ask you**:
- Off-chain monitoring infrastructure?
- Monitoring plan documented?
- Incident response plan exists and tested?

**WEAK if**:
- No event strategy
- Events missing for critical updates
- No consistent event guidelines
- Same events reused for different purposes

**MODERATE requires**:
- All weak criteria resolved
- Events for all critical functions
- Off-chain monitoring logs events
- Monitoring plan documented
- Event documentation (purpose, usage, assumptions)
- Log review process documented
- Incident response plan exists

**SATISFACTORY requires**:
- All moderate criteria met
- Monitoring triggers alerts on unexpected behavior
- Defined roles for incident detection
- Incident response plan regularly tested

---

### 3. AUTHENTICATION / ACCESS CONTROLS
**Focus**: Privilege management, role separation, access patterns

**I'll analyze**:
- Access control modifiers/functions
- Role definitions and separation
- Admin/owner patterns
- Privileged function implementations
- Test coverage for access controls

**I'll ask you**:
- Who are privileged actors? (EOA, multisig, DAO?)
- Documentation of roles and privileges?
- Key compromise scenarios?

**WEAK if**:
- Access controls unclear or inconsistent
- Single address controls system without safeguards
- Missing access controls on privileged functions
- No role differentiation
- All privileges on one address

**MODERATE requires**:
- All weak criteria resolved
- All privileged functions have access control
- Least privilege principle followed
- Non-overlapping role privileges
- Clear actor/privilege documentation
- Tests cover all privileges
- Roles can be revoked
- Two-step processes for EOA operations

**SATISFACTORY requires**:
- All moderate criteria met
- All actors well documented
- Implementation matches specification
- Privileged actors not EOAs
- Key leakage doesn't compromise system
- Tested against known attack vectors

---

### 4. COMPLEXITY MANAGEMENT
**Focus**: Code clarity, function scope, avoiding unnecessary complexity

**I'll analyze**:
- Function length and nesting depth
- Cyclomatic complexity
- Code duplication
- Inheritance hierarchies
- Naming conventions
- Function clarity

**I'll ask you**:
- Complex parts documented?
- Naming convention documented?
- Complexity measurements?

**WEAK if**:
- Unnecessary complexity hinders review
- Functions overuse nested operations
- Functions have unclear scope
- Unnecessary code duplication
- Complex inheritance tree

**MODERATE requires**:
- All weak criteria resolved
- Complex parts identified, minimized
- High complexity (≥11) justified
- Critical functions well-scoped
- Minimal, justified redundancy
- Clear inputs with validation
- Documented naming convention
- Types not misused

**SATISFACTORY requires**:
- All moderate criteria met
- Minimal unnecessary complexity
- Necessary complexity documented
- Clear function purposes
- Straightforward to test
- No redundant behavior

---

### 5. DECENTRALIZATION
**Focus**: Centralization risks, upgrade control, user opt-out

**I'll analyze**:
- Upgrade mechanisms (proxies, governance)
- Owner/admin control scope
- Timelock/multisig patterns
- User opt-out mechanisms

**I'll ask you**:
- Upgrade mechanism and control?
- User opt-out/exit paths?
- Centralization risk documentation?

**WEAK if**:
- Centralization points not visible to users
- Critical functions upgradable by single entity without opt-out
- Single entity controls user funds
- All decisions by single entity
- Parameters changeable anytime by single entity
- Centralized permission required

**MODERATE requires**:
- All weak criteria resolved
- Centralization risks identified, justified, documented
- User opt-out/exit path documented
- Upgradeability only for non-critical features
- Privileged actors can't unilaterally move/trap funds
- All privileges documented

**SATISFACTORY requires**:
- All moderate criteria met
- Clear decentralization path justified
- On-chain voting risks addressed OR no centralization
- Deployment risks documented
- External interaction risks documented
- Critical parameters immutable OR users can exit

---

### 6. DOCUMENTATION
**Focus**: Specifications, architecture, user stories, inline comments

**I'll analyze**:
- README, specification, architecture docs
- Inline code comments (NatSpec, rustdoc, etc.)
- User stories
- Glossaries
- Documentation completeness and accuracy

**I'll ask you**:
- User stories documented?
- Architecture diagrams exist?
- Glossary for domain terms?

**WEAK if**:
- Minimal or incomplete/outdated documentation
- Only high-level description
- Code comments don't match docs
- Not publicly available (for public codebases)
- Unexplained artificial terms

**MODERATE requires**:
- All weak criteria resolved
- Clear, unambiguous writing
- Glossary for business terms
- Architecture diagrams
- User stories included
- Core/critical components identified
- Docs sufficient to understand behavior
- All critical functions/blocks documented
- Known risks/limitations documented

**SATISFACTORY requires**:
- All moderate criteria met
- User stories cover all operations
- Detailed behavior descriptions
- Implementation matches spec (deviations justified)
- Invariants clearly defined
- Consistent naming conventions
- Documentation for end-users AND developers

---

### 7. TRANSACTION ORDERING RISKS
**Focus**: MEV, front-running, sandwich attacks

**I'll analyze**:
- MEV-vulnerable patterns (AMM swaps, arbitrage, large trades)
- Front-running protections
- Slippage/deadline checks
- Oracle implementations

**I'll ask you**:
- Transaction ordering risks identified/documented?
- Known MEV opportunities?
- Mitigation strategies?
- Testing for ordering attacks?

**WEAK if**:
- Ordering risks not identified/documented
- Protocols/assets at risk from unexpected ordering
- Relies on unjustified MEV prevention constraints
- Unproven assumptions about MEV extractors

**MODERATE requires**:
- All weak criteria resolved
- User operation ordering risks limited, justified, documented
- MEV mitigations in place (delays, slippage checks)
- Testing emphasizes ordering risks
- Tamper-resistant oracles used

**SATISFACTORY requires**:
- All moderate criteria met
- All ordering risks documented and justified
- Known risks highlighted in docs/tests, visible to users
- Documentation centralizes MEV opportunities
- Privileged operation ordering risks limited, justified
- Tests highlight ordering risks

---

### 8. LOW-LEVEL MANIPULATION
**Focus**: Assembly, unsafe code, low-level operations

**I'll analyze**:
- Assembly blocks
- Unsafe code sections
- Low-level calls
- Bitwise operations
- Justification and documentation

**I'll ask you**:
- Why use assembly/unsafe here?
- High-level reference implementation?
- How is this tested?

**WEAK if**:
- Unjustified low-level manipulations
- Assembly/low-level not justified, could be high-level

**MODERATE requires**:
- All weak criteria resolved
- Assembly use limited and justified
- Inline comments for each operation
- No re-implementation of established libraries without justification
- High-level reference for complex assembly

**SATISFACTORY requires**:
- All moderate criteria met
- Thorough documentation/justification/testing
- Validated with automated testing vs reference
- Differential fuzzing compares implementations
- Compiler optimization risks identified

---

### 9. TESTING AND VERIFICATION
**Focus**: Coverage, testing techniques, CI/CD

**I'll analyze**:
- Test file count and organization
- Test coverage reports
- CI/CD configuration
- Advanced testing (fuzzing, formal verification)
- Test quality and isolation

**I'll ask you**:
- Test coverage percentage?
- Do all tests pass?
- Testing techniques used?
- Easy to run tests?

**WEAK if**:
- Limited testing, only happy paths
- Common use cases not tested
- Tests fail
- Can't run tests "out of the box"

**MODERATE requires**:
- All weak criteria resolved
- Most functions/use cases tested
- All tests pass
- Coverage reports available
- Automated testing for critical components
- Tests in CI/CD
- Integration tests (if applicable)
- Test code follows best practices

**SATISFACTORY requires**:
- All moderate criteria met
- 100% reachable branch/statement coverage
- End-to-end testing covers all entry points
- Isolated test cases (no dependencies)
- Mutation testing used
