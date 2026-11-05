## Assessment Areas

### 1. DOCUMENTATION & SPECIFICATIONS

**What I'll do**:
- Read existing documentation (README, specs, comments)
- Analyze contract/module purposes and interactions
- Identify undocumented assumptions
- For Solidity projects: check NatSpec completeness
- Generate architectural diagrams using Slither printers (if available)

**I'll generate**:
- Plain English system description
- Contract interaction diagrams
- State machine diagrams (where applicable)
- Documentation gaps list

**Best practices**:
- Every contract should have a clear purpose statement
- All assumptions should be explicitly documented
- Critical functions should have detailed documentation
- System interactions should be visualized
- State transitions should be clear

---

### 2. ON-CHAIN vs OFF-CHAIN COMPUTATION

**What I'll analyze**:
- Current on-chain logic complexity
- Data processing patterns
- Verification vs computation patterns

**I'll look for**:
- Complex computations that could move off-chain
- Sorting/ordering operations done on-chain
- Data preprocessing opportunities
- Gas optimization potential

**I'll suggest**:
- Off-chain preprocessing with on-chain verification
- Data structure optimizations
- Gas-efficient architectural changes

**Note**: Only applicable if your project has off-chain components or could benefit from them. I won't hallucinate this if it's not relevant.

---

### 3. UPGRADEABILITY

**What I'll check**:
- Does the project support upgrades?
- What upgradeability pattern is used?
- Is the approach documented?

**I'll analyze**:
- Migration vs upgradeability trade-offs
- Data separation vs delegatecall proxy patterns
- Upgrade/migration procedure documentation
- Deployment and initialization scripts

**I'll recommend**:
- Whether migration might be better than upgradeability
- Data separation pattern if suitable
- Documenting the upgrade procedure before deployment

**Best practices**:
- Favor contract migration over upgradeability
- Use data separation instead of delegatecall proxy when possible
- Document migration/upgrade procedure including:
  - Calls to initiate new contracts
  - Key storage locations and access methods
  - Deployment verification scripts

**Note**: Only applicable if your project has or plans upgradeability. I'll skip this if not relevant.

---

### 4. DELEGATECALL PROXY PATTERN

**What I'll check**:
- Is delegatecall used for proxies?
- Storage layout consistency
- Inheritance order implications
- Initialization patterns

**I'll analyze for**:

**Storage Layout**:
- Proxy and implementation storage compatibility
- Shared base contract for state variables
- Storage slot conflicts

**Inheritance**:
- Inheritance order consistency
- Storage layout effects from inheritance changes

**Initialization**:
- Implementation initialization status
- Front-running risks
- Factory pattern usage

**Function Shadowing**:
- Same methods on proxy and implementation
- Administrative function shadowing
- Call routing correctness

**Direct Implementation Usage**:
- Implementation state protection
- Direct usage prevention mechanisms
- Self-destruct risks

**Immutable/Constant Variables**:
- Sync between proxy and implementation
- Bytecode embedding issues

**Contract Existence Checks**:
- Low-level call protections
- Empty bytecode handling
- Constructor execution considerations

**Tools I'll use**:
- Slither's `slither-check-upgradeability` (if available)
- Manual pattern analysis

**Note**: Only applicable if delegatecall proxies are present. I'll skip this if not relevant.

---

### 5. FUNCTION COMPOSITION

**What I'll analyze**:
- System logic organization
- Function sizes and purposes
- Code modularity

**I'll look for**:
- Large functions doing too many things
- Unclear function purposes
- Logic that could be better separated
- Grouping opportunities (authentication, arithmetic, etc.)

**I'll recommend**:
- Function splitting for clarity
- Logical grouping strategies
- Component isolation for testing

**Best practices**:
- Divide system logic through contracts or function groups
- Write small functions with clear purposes
- Make code easy to review and test

---

### 6. INHERITANCE

**What I'll check**:
- Inheritance tree depth and width
- Inheritance complexity

**I'll analyze**:
- Inheritance hierarchy using Slither (if available)
- Diamond problem risks
- Override patterns
- Virtual function usage

**I'll recommend**:
- Simplifying complex hierarchies
- Flattening when appropriate
- Clear inheritance documentation

**Best practices**:
- Keep inheritance manageable
- Minimize depth and width
- Use Slither's inheritance printer to visualize

---

### 7. EVENTS

**What I'll check**:
- Events for critical operations
- Event completeness
- Event naming consistency

**I'll look for**:
- Critical operations without events
- Inconsistent event patterns
- Missing indexed parameters
- Event documentation

**I'll recommend**:
- Adding events for critical operations:
  - State changes
  - Transfers
  - Access control changes
  - Parameter updates
- Event naming conventions
- Indexed parameters for filtering

**Best practices**:
- Log all critical operations
- Events facilitate debugging during development
- Events enable monitoring after deployment

---

### 8. COMMON PITFALLS

**What I'll check**:
- Known vulnerability patterns
- Platform-specific issues
- Language-specific gotchas

**I'll analyze for**:
- Reentrancy patterns
- Integer overflow/underflow (pre-0.8 Solidity)
- Access control issues
- Front-running vulnerabilities
- Oracle manipulation risks
- Timestamp dependence
- Uninitialized variables
- Delegatecall risks
- Platform-specific pitfalls

**Resources I reference**:
- Not So Smart Contracts (Trail of Bits)
- Solidity documentation warnings
- Platform-specific vulnerability databases

**I'll recommend**:
- Specific fixes for identified issues
- Prevention patterns
- Security review resources

---

### 9. DEPENDENCIES

**What I'll analyze**:
- External libraries used
- Library versions
- Dependency management approach
- Copy-pasted code

**I'll check for**:
- Well-tested libraries (OpenZeppelin, etc.)
- Dependency manager usage
- Outdated dependencies
- Copied code instead of imports
- Custom implementations of standard functionality

**I'll recommend**:
- Using established libraries
- Dependency manager setup
- Updating outdated dependencies
- Replacing copied code with imports

**Best practices**:
- Use well-tested libraries
- Use dependency manager (npm, forge, cargo, etc.)
- Keep external sources up-to-date
- Avoid reinventing the wheel

---

### 10. TESTING & VERIFICATION

**What I'll analyze**:
- Test files and coverage
- Testing techniques used
- CI/CD setup
- Automated security testing

**I'll check for**:
- Unit test completeness
- Integration tests
- Edge case testing
- Slither checks
- Fuzzing (Echidna, Foundry, AFL, etc.)
- Formal verification
- CI/CD configuration

**I'll recommend**:
- Test coverage improvements
- Advanced testing techniques:
  - Fuzzing with Echidna or Foundry
  - Custom Slither detectors
  - Formal verification properties
  - Mutation testing
- CI/CD integration
- Pre-deployment verification scripts

**Best practices**:
- Create thorough unit tests
- Develop custom Slither and Echidna checks
- Automate security testing in CI

---

### 11. PLATFORM-SPECIFIC GUIDANCE

#### Solidity Projects

**I'll check**:
- Solidity version used
- Compiler warnings
- Inline assembly usage

**I'll recommend**:
- Stable Solidity versions (per Slither recommendations)
- Compiling with stable version
- Checking warnings with latest version
- Avoiding inline assembly without EVM expertise

**Best practices**:
- Favor Solidity 0.8.x for overflow protection
- Compile with stable release
- Check for warnings with latest release
- Avoid inline assembly unless absolutely necessary

#### Other Platforms

**I'll provide**:
- Platform-specific best practices
- Tool recommendations
- Security considerations

---
