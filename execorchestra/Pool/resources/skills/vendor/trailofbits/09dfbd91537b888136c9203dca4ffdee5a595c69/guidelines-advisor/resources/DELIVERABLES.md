
## Deliverables

### 1. System Documentation

**Plain English Description**:
```
[Project Name] System Overview

Purpose:
[Clear description of what the system does]

Components:
[List of contracts/modules and their roles]

Assumptions:
[Explicit assumptions about the codebase, environment, users]

Interactions:
[How components interact with each other]

Critical Operations:
[Key operations and their purposes]
```

**Architectural Diagrams**:
- Contract inheritance graph
- Contract interaction graph
- State machine diagram (if applicable)

**Code Documentation Gaps**:
- List of undocumented functions
- Missing NatSpec/documentation
- Unclear assumptions

---

### 2. Architecture Analysis

**On-Chain/Off-Chain Assessment**:
- Current distribution
- Optimization opportunities
- Gas savings potential
- Complexity reduction suggestions

**Upgradeability Review**:
- Current approach assessment
- Alternative patterns consideration
- Procedure documentation status
- Recommendations

**Proxy Pattern Review** (if applicable):
- Security assessment
- Slither-check-upgradeability findings
- Specific risks identified
- Mitigation recommendations

---

### 3. Implementation Review

**Function Composition**:
- Complex functions requiring splitting
- Logic grouping suggestions
- Modularity improvements

**Inheritance**:
- Hierarchy visualization
- Complexity assessment
- Simplification recommendations

**Events**:
- Missing events list
- Event improvements
- Monitoring setup suggestions

**Pitfalls**:
- Identified vulnerabilities
- Severity assessment
- Fix recommendations

**Dependencies**:
- Library assessment
- Update recommendations
- Dependency management suggestions

**Testing**:
- Coverage analysis
- Testing gaps
- Advanced technique recommendations
- CI/CD suggestions

---

### 4. Prioritized Recommendations

**CRITICAL** (address immediately):
- Security vulnerabilities
- Proxy implementation issues
- Missing critical events
- Broken upgrade paths

**HIGH** (address before deployment):
- Documentation gaps
- Testing improvements
- Dependency updates
- Architecture optimizations

**MEDIUM** (address for production quality):
- Code organization
- Event completeness
- Function clarity
- Inheritance simplification

**LOW** (nice to have):
- Additional tests
- Documentation enhancements
- Gas optimizations
