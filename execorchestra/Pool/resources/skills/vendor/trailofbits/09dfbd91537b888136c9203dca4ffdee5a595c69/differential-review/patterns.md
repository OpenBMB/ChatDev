# Common Vulnerability Patterns

Quick reference for detecting common security issues in code changes.

**Specialized Pattern Resources:**
For specific contexts, reference these additional pattern databases:

**Domain-Specific:**
- `domain-specific-audits/defi-bridges/resources/` - 127 bridge-specific findings
- `domain-specific-audits/tick-math/resources/` - 81 tick math findings
- `domain-specific-audits/merkle-trees/resources/` - 67 merkle tree findings
- [Check `domain-specific-audits/skills/` for additional domains]

**Solidity-Specific:**
- `not-so-smart-contracts` - Automated Solidity vulnerability detectors
- `token-integration-analyzer` - Token integration safety patterns
- `building-secure-contracts/development-guidelines` - Solidity best practices

These complement the generic patterns below.

---

## Security Regressions

**Pattern:** Previously removed code is re-added

**Detection:**
```bash
# Code previously removed for security
git log -S "pattern" --all --grep="security\|fix\|CVE"
```

**Red flags:**
- Commit message contains "security", "fix", "CVE", "vulnerability"
- Code removed <6 months ago
- No explanation in current PR for re-addition

**Example:**
```solidity
// Removed in commit abc123 "Fix reentrancy CVE-2024-1234"
// Re-added in current PR
function emergencyWithdraw() {
    // REGRESSION: Reentrancy vulnerability re-introduced
}
```

---

## Double Decrease/Increase Bugs

**Pattern:** Same accounting operation twice for same event

**Detection:** Look for two state updates in related functions for same logical action

**Example:**
```solidity
// Request exit
function requestExit() {
    balance[user] -= amount;  // First decrease
}

// Process exit
function processExit() {
    balance[user] -= amount;  // Second decrease - BUG!
}
```

**Impact:** User balance decremented twice, protocol loses funds

---

## Missing Validation

**Pattern:** Removed `require`/`assert`/`check` without replacement

**Detection:**
```bash
git diff <range> | grep "^-.*require"
git diff <range> | grep "^-.*assert"
git diff <range> | grep "^-.*revert"
```

**Questions to ask:**
- Was validation moved elsewhere?
- Is it redundant (defensive programming)?
- Does removal expose vulnerability?

**Example:**
```diff
function withdraw(uint256 amount) {
-   require(amount > 0, "Zero amount");
-   require(amount <= balance[msg.sender], "Insufficient");
    balance[msg.sender] -= amount;
}
```

**Risk:** Zero-amount withdrawals, underflow attacks now possible

---

## Underflow/Overflow

**Pattern:** Arithmetic without SafeMath or checks

**Detection:**
- Look for `+`, `-`, `*`, `/` in Solidity <0.8.0
- Check if SafeMath removed
- Look for unchecked blocks in Solidity >=0.8.0

**Example:**
```solidity
// Solidity 0.7 without SafeMath
balance[user] -= amount;  // Can underflow if amount > balance

// Solidity 0.8+ with unchecked
unchecked {
    balance[user] -= amount;  // Deliberately bypasses overflow check
}
```

**Risk:** Integer wrap-around leads to incorrect balances

---

## Reentrancy

**Pattern:** External call before state update

**Detection:** Look for CEI (Checks-Effects-Interactions) pattern violations

**Example:**
```solidity
// VULNERABLE: External call before state update
function withdraw() {
    uint amount = balances[msg.sender];
    (bool success,) = msg.sender.call{value: amount}("");  // External call FIRST
    require(success);
    balances[msg.sender] = 0;  // State update AFTER
}

// SAFE: State update before external call
function withdraw() {
    uint amount = balances[msg.sender];
    balances[msg.sender] = 0;  // State update FIRST
    (bool success,) = msg.sender.call{value: amount}("");  // External call AFTER
    require(success);
}
```

**Impact:** Attacker can recursively call withdraw() before balance is zeroed

---

## Access Control Bypass

**Pattern:** Removed or relaxed permission checks

**Detection:**
```bash
git diff <range> | grep "^-.*onlyOwner"
git diff <range> | grep "^-.*onlyAdmin"
git diff <range> | grep "^-.*require.*msg.sender"
```

**Questions:**
- Who can now call this function?
- What's the new trust model?
- Was check moved to caller?

**Example:**
```diff
- function setConfig(uint value) external onlyOwner {
+ function setConfig(uint value) external {
      config = value;
  }
```

**Risk:** Any user can now modify critical configuration

---

## Race Conditions / Front-Running

**Pattern:** State-dependent logic without protection

**Detection:** Look for two-step processes without commit-reveal or timelocks

**Example:**
```solidity
// Step 1: Approve
function approve(address spender, uint amount) {
    allowance[msg.sender][spender] = amount;
}

// Step 2: User can front-run between approval changes
// Attacker sees tx changing approval from 100 to 50
// Front-runs to spend 100, then spends 50 after = 150 total
```

**Risk:** MEV/front-running exploits state transitions

---

## Timestamp Manipulation

**Pattern:** Security logic depending on `block.timestamp`

**Detection:**
```bash
grep -r "block.timestamp" --include="*.sol"
grep -r "now\b" --include="*.sol"  # Solidity <0.7
```

**Example:**
```solidity
// VULNERABLE
require(block.timestamp > deadline, "Too early");
// Miner can manipulate timestamp by ~15 seconds

// SAFER
require(block.number > deadlineBlock, "Too early");
// Block numbers are harder to manipulate
```

**Risk:** Miners can manipulate timestamps within tolerance

---

## Unchecked Return Values

**Pattern:** External call without checking success

**Detection:**
```bash
git diff <range> | grep "\.call\|\.send\|\.transfer"
```

**Example:**
```solidity
// VULNERABLE
token.transfer(user, amount);  // Ignores return value

// SAFE
require(token.transfer(user, amount), "Transfer failed");
// Or use SafeERC20 wrapper
```

**Risk:** Silent failures lead to inconsistent state

---

## Denial of Service

**Pattern:** Unbounded loops, external call reverts blocking execution

**Detection:**
- Arrays that grow without limit
- Loops over user-controlled array
- Critical function depends on external call success

**Example:**
```solidity
// DOS: Attacker adds many users, making loop too expensive
function distributeRewards() {
    for (uint i = 0; i < users.length; i++) {
        users[i].transfer(reward);  // Runs out of gas
    }
}
```

**Risk:** Function becomes unusable due to gas limits

---

## Quick Detection Commands

**Find removed security checks:**
```bash
git diff <range> | grep "^-" | grep -E "require|assert|revert"
```

**Find new external calls:**
```bash
git diff <range> | grep "^+" | grep -E "\.call|\.delegatecall|\.staticcall"
```

**Find changed access modifiers:**
```bash
git diff <range> | grep -E "onlyOwner|onlyAdmin|internal|private|public|external"
```

**Find arithmetic changes:**
```bash
git diff <range> | grep -E "\+|\-|\*|/"
```

---

**For detailed analysis workflow, see [methodology.md](methodology.md)**
**For building exploit scenarios, see [adversarial.md](adversarial.md)**
