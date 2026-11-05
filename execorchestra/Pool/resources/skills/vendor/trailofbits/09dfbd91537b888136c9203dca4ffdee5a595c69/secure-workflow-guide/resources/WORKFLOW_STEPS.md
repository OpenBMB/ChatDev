## The 5-Step Workflow

### Step 1: Check for Known Security Issues

I'll run Slither with 70+ built-in detectors:

```bash
slither . --exclude-dependencies
```

Then I'll:
- Parse findings by severity
- Explain each issue with file references
- Recommend fixes
- Help you triage false positives

**Goal**: Clean Slither report or documented triages

---

### Step 2: Check Special Features

I'll detect what's applicable and run the right tools:

**If upgradeable contracts**:
```bash
slither-check-upgradeability . ContractName --proxy-name ProxyName
```
Checks 17 ways upgrades can go wrong

**If ERC tokens (ERC20, ERC721, etc.)**:
```bash
slither-check-erc . ContractName --erc erc20
```
Validates conformance to 6 common specs

**If Truffle tests exist**:
```bash
slither-prop . --contract ContractName
```
Generates security properties for ERC20

**If integrating third-party tokens**:
I'll recommend using the `token-integration-analyzer` skill

**Note**: I'll only run checks that apply to your codebase

---

### Step 3: Visual Security Inspection

I'll generate 3 security diagrams:

**Inheritance Graph**:
```bash
slither . --print inheritance-graph
```
Identifies shadowing and C3 linearization issues

**Function Summary**:
```bash
slither . --print function-summary
```
Shows function visibility and access controls

**Variables and Authorization**:
```bash
slither . --print vars-and-auth
```
Maps who can write to state variables

I'll review each diagram with you and highlight security concerns

---

### Step 4: Document Security Properties

I'll help you document critical security properties:

**Properties to Define**:
- **State machine**: Valid transitions, invariants
- **Access controls**: Who can call what
- **Arithmetic**: Overflow protection, precision
- **External interactions**: Reentrancy, failed calls
- **Standards conformance**: ERC requirements

**Then Set Up Testing**:

**Echidna (fuzzing)**:
- Create property test contract
- Define invariants in Solidity
- Configure echidna.yaml
- Run fuzzing campaign

**Manticore (formal verification)**:
- Define properties in Solidity or Python
- Set up symbolic execution
- Validate critical paths

**Custom Slither Checks**:
- Use Slither Python API for project-specific patterns
- Focus on business logic

**Note**: This is the most important activity for security but requires learning

---

### Step 5: Manual Review Areas

I'll analyze areas automated tools miss:

**Privacy Considerations**:
- Are secrets stored on-chain?
- Is commit-reveal needed?
- Are assumptions about privacy documented?

**Front-Running Risks**:
- Price-sensitive transactions without slippage protection?
- Ordering-dependent logic?
- MEV opportunities?

**Cryptographic Operations**:
- Weak randomness (block.timestamp, blockhash)?
- Signature verification issues (ecrecover misuse)?
- Hash collision vulnerabilities?

**DeFi Interactions**:
- Oracle manipulation risks?
- Flash loan attack vectors?
- Protocol assumption violations?

I'll search your codebase for these patterns and flag risks
