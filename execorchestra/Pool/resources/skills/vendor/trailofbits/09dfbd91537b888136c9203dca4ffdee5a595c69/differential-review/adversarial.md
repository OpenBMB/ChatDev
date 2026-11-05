# Adversarial Vulnerability Analysis (Phase 5)

Structured methodology for finding vulnerabilities through attacker modeling.

**When to use:** After completing deep context analysis (Phase 4), apply this to all HIGH RISK changes.

---

## 1. Define Specific Attacker Model

**WHO is the attacker?**
- Unauthenticated external user
- Authenticated regular user
- Malicious administrator
- Compromised contract/service
- Front-runner/MEV bot

**WHAT access/privileges do they have?**
- Public API access only
- Authenticated user role
- Specific permissions/tokens
- Contract call capabilities

**WHERE do they interact with the system?**
- Specific HTTP endpoints
- Smart contract functions
- RPC interfaces
- External APIs

---

## 2. Identify Concrete Attack Vectors

```
ENTRY POINT: [Exact function/endpoint attacker can access]

ATTACK SEQUENCE:
1. [Specific API call/transaction with parameters]
2. [How this reaches the vulnerable code]
3. [What happens in the vulnerable code]
4. [Impact achieved]

PROOF OF ACCESSIBILITY:
- Show the function is public/external
- Demonstrate attacker has required permissions
- Prove attack path exists through actual interfaces
```

---

## 3. Rate Realistic Exploitability

**EASY:** Exploitable via public APIs with no special privileges
- Single transaction/call
- Common user access level
- No complex conditions required

**MEDIUM:** Requires specific conditions or elevated privileges
- Multiple steps or timing requirements
- Elevated but obtainable privileges
- Specific system state needed

**HARD:** Requires privileged access or rare conditions
- Admin/owner privileges needed
- Rare edge case conditions
- Significant resources required

---

## 4. Build Complete Exploit Scenario

```
ATTACKER STARTING POSITION:
[What the attacker has at the beginning]

STEP-BY-STEP EXPLOITATION:
Step 1: [Concrete action through accessible interface]
  - Command: [Exact call/request]
  - Parameters: [Specific values]
  - Expected result: [What happens]

Step 2: [Next action]
  - Command: [Exact call/request]
  - Why this works: [Reference to code change]
  - System state change: [What changed]

Step 3: [Final impact]
  - Result: [Concrete harm achieved]
  - Evidence: [How to verify impact]

CONCRETE IMPACT:
[Specific, measurable impact - not "could cause issues"]
- Exact amount of funds drained
- Specific privileges escalated
- Particular data exposed
```

---

## 5. Cross-Reference with Baseline Context

From baseline analysis (see [methodology.md](methodology.md#pre-analysis-baseline-context-building)), check:
- Does this violate a system-wide invariant?
- Does this break a trust boundary?
- Does this bypass a validation pattern?
- Is this a regression of a previous fix?

---

## Vulnerability Report Template

Generate this for each finding:

```markdown
## [SEVERITY] Vulnerability Title

**Attacker Model:**
- WHO: [Specific attacker type]
- ACCESS: [Exact privileges]
- INTERFACE: [Specific entry point]

**Attack Vector:**
[Step-by-step exploit through accessible interfaces]

**Exploitability:** EASY/MEDIUM/HARD
**Justification:** [Why this rating]

**Concrete Impact:**
[Specific, measurable harm - not theoretical]

**Proof of Concept:**
```code
// Exact code to reproduce
```

**Root Cause:**
[Reference specific code change at file.sol:L123]

**Blast Radius:** [N callers affected]
**Baseline Violation:** [Which invariant/pattern broken]
```

---

## Example: Complete Adversarial Analysis

**Change:** Removed `require(amount > 0)` check from `withdraw()` function

### 1. Attacker Model
- **WHO:** Unauthenticated external user
- **ACCESS:** Can call public contract functions
- **INTERFACE:** `withdraw(uint256 amount)` at 0x1234...

### 2. Attack Vector
**ENTRY POINT:** `withdraw(0)`

**ATTACK SEQUENCE:**
1. Call `withdraw(0)` from attacker address
2. Code bypasses amount check (removed)
3. Withdraw event emitted with 0 amount
4. Accounting updated incorrectly

**PROOF:** Function is `external`, no auth required

### 3. Exploitability
**RATING:** EASY
- Single transaction
- Public function
- No special state required

### 4. Exploit Scenario
**ATTACKER POSITION:** Has user account with 0 balance

**EXPLOITATION:**
```solidity
Step 1: attacker.withdraw(0)
  - Passes removed validation
  - Emits Withdraw(user, 0)
  - Updates withdrawnAmount[user] += 0

Step 2: Off-chain indexer sees Withdraw event
  - Credits attacker for 0 withdrawal
  - But accounting thinks withdrawal happened

Step 3: Accounting mismatch exploited
  - Total supply decremented
  - User balance not changed
  - System invariants broken
```

**IMPACT:**
- Protocol accounting corrupted
- Can be used to manipulate LP calculations
- Estimated $50K impact on pool prices

### 5. Baseline Violation
- Violates invariant: "All withdrawals must transfer non-zero value"
- Breaks validation pattern: Amount checks present in all other value transfers
- Regression: Check added in commit abc123 "Fix zero-amount exploit"

---

**Next:** Document all findings in final report (see [reporting.md](reporting.md))
