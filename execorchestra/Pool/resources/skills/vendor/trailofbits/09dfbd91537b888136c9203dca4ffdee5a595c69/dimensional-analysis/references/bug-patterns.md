# Dimensional Bug Patterns

This document catalogs common dimensional bugs with examples and detection strategies. Examples use Solidity syntax, but these bug patterns occur in any language performing arithmetic with mixed units and scaling factors (Rust, TypeScript, Python, etc.).

## Critical Bugs (P0)

### Pattern 1: Unit Mismatch in Price Feeds

**Description:** Oracle returns price in different precision than expected.

**Example:**
```solidity
// Contract assumes D27 prices
uint256 price; // D27{UoA/tok}

// But Chainlink returns D8!
(, int256 answer,,,) = priceFeed.latestRoundData();
price = uint256(answer); // BUG: D8 assigned to D27 variable

// Correct:
price = uint256(answer) * 1e19; // Scale D8 to D27
```

**Impact:** Price values off by 10^19, causing catastrophic mispricing.

**Detection:** Check oracle `decimals()` vs expected precision.

---

### Pattern 2: Cross-Contract Dimension Assumption Mismatch

**Description:** Caller assumes different dimension than callee returns.

**Example:**
```solidity
// Protocol A's Vault
function getSharePrice() external returns (uint256) {
    return totalAssets * 1e18 / totalShares; // Returns D18{tok/share}
}

// Protocol B consuming it
uint256 sharePrice; // D27{tok/share} - WRONG ASSUMPTION
sharePrice = vaultA.getSharePrice(); // BUG: D18 value in D27 variable

// Correct:
sharePrice = vaultA.getSharePrice() * 1e9;
```

**Impact:** 9 orders of magnitude error in calculations.

**Detection:** Compare interface documentation and actual return dimensions.

---

### Pattern 3: Adding Incompatible Dimensions

**Description:** Adding values with different semantic meanings.

**Example:**
```solidity
// User's position
uint256 tokenBalance;  // {tok}
uint256 shareBalance;  // {share}

// BUG: Can't add tokens and shares!
uint256 totalPosition = tokenBalance + shareBalance;

// Correct: Convert to common dimension
uint256 totalTokens = tokenBalance + convertToAssets(shareBalance);
```

**Impact:** Result is mathematically meaningless.

**Detection:** Verify both operands have identical dimensions.

---

### Pattern 4: Wrong Precision Causing Overflow

**Description:** Multiplication without scaling causes overflow or precision explosion.

**Example:**
```solidity
uint256 amount; // D18{tok}
uint256 price;  // D27{UoA/tok}

// BUG: D18 * D27 = D45, overflows!
uint256 value = amount * price;

// Correct:
uint256 value = Math.mulDiv(amount, price, 1e27); // Result: D18{UoA}
```

**Impact:** Overflow reverts or silent wraparound.

**Detection:** Track precision through multiplication chains.

---

## High Severity Bugs (P1)

### Pattern 5: Missing Scaling Factor

**Description:** Calculation omits necessary precision adjustment.

**Example:**
```solidity
// Calculate shares from deposit
uint256 assets;     // D18{tok}
uint256 supply;     // D18{share}
uint256 totalAssets; // D18{tok}

// BUG: Missing D18 scaling
uint256 shares = assets * supply / totalAssets;
// Actually: D18 * D18 / D18 = D18, but intermediate is D36!

// Correct:
uint256 shares = Math.mulDiv(assets, supply, totalAssets);
```

**Impact:** Precision loss or overflow in intermediate calculation.

**Detection:** Verify all multiplications are properly scaled.

---

### Pattern 6: Wrong Scaling Direction

**Description:** Multiply when should divide, or vice versa.

**Example:**
```solidity
uint256 priceD27; // D27{UoA/tok}

// BUG: Multiplied instead of divided
uint256 priceD18 = priceD27 * 1e9; // Now D36!

// Correct:
uint256 priceD18 = priceD27 / 1e9;
```

**Impact:** Value off by 10^18.

**Detection:** Verify scaling direction matches precision conversion intent.

---

### Pattern 7: Inconsistent Return Path Dimensions

**Description:** Different code paths return values with different dimensions.

**Example:**
```solidity
function getValue(bool useOracle) returns (uint256) {
    if (useOracle) {
        return oracle.getPrice(token); // D8{UoA/tok}
    } else {
        return cachedPrice; // D18{UoA/tok} - DIFFERENT DIMENSION!
    }
}
```

**Impact:** Callers receive inconsistent values.

**Detection:** Trace all return paths and verify dimensions match.

---

### Pattern 8: Implicit Precision Truncation

**Description:** High precision value assigned to lower precision variable.

**Example:**
```solidity
uint256 preciseValue; // D27{UoA}
uint256 result;       // D18{UoA}

// BUG: Truncates 9 decimal places
result = preciseValue / 1e9;

// If preciseValue = 1.5e27 (1.5 in D27)
// result = 1.5e18 (1.5 in D18) - OK
// But if preciseValue = 1e18 (tiny in D27)
// result = 1e9 (still tiny in D18, lost precision)
```

**Impact:** Small values may become zero.

**Detection:** Identify precision reductions and check for rounding issues.

---

## Medium Severity Bugs (P2)

### Pattern 9: Redundant Scaling

**Description:** Unnecessary conversion that wastes gas or introduces rounding.

**Example:**
```solidity
uint256 priceD18; // D18{UoA/tok}

// Redundant: scale up then down
uint256 temp = priceD18 * 1e9;  // D27
uint256 result = temp / 1e9;    // Back to D18

// Could just use priceD18 directly
```

**Impact:** Gas waste, possible rounding errors.

**Detection:** Identify inverse scaling operations.

---

### Pattern 10: Fee Applied to Wrong Dimension

**Description:** Fee percentage applied to value instead of amount, or vice versa.

**Example:**
```solidity
uint256 depositAmount; // {tok}
uint256 feePercent;    // D18{1}
uint256 pricePerToken; // D27{UoA/tok}

// BUG: Fee on USD value, not token amount
uint256 fee = depositAmount * pricePerToken * feePercent / 1e45;

// Correct: Fee on token amount
uint256 fee = depositAmount * feePercent / 1e18; // {tok}
```

**Impact:** Fee calculation incorrect, may over/under charge.

**Detection:** Verify fee is applied to intended base.

---

### Pattern 11: Time Unit Confusion

**Description:** Mixing seconds with other time units.

**Example:**
```solidity
uint256 ratePerYear;  // D18{1} annual rate
uint256 elapsed;      // {s} seconds

// BUG: Applying annual rate to seconds
uint256 accrued = principal * ratePerYear * elapsed / 1e18;

// Correct: Convert to per-second rate
uint256 SECONDS_PER_YEAR = 365.25 days;
uint256 ratePerSecond = ratePerYear / SECONDS_PER_YEAR;
uint256 accrued = principal * ratePerSecond * elapsed / 1e18;
```

**Impact:** Interest/fees off by ~31.5 million.

**Detection:** Verify time unit consistency in rate calculations.

---

### Pattern 12: Division Before Multiplication

**Description:** Dividing first causes precision loss.

**Example:**
```solidity
uint256 a = 100;
uint256 b = 3;
uint256 c = 7;

// BUG: Division truncates
uint256 result = a / b * c; // = 33 * 7 = 231

// Correct:
uint256 result = a * c / b; // = 700 / 3 = 233
```

**Impact:** Silent precision loss.

**Detection:** Reorder to multiply before divide, or use mulDiv.

---

## Common Traps

These traps catch even experienced auditors. Always verify explicitly.

### Trap 1: Assumed Dimensionless Constant

```solidity
// Is this correct?
uint256 result = amount * MULTIPLIER / DIVISOR;

// Question: Are MULTIPLIER and DIVISOR truly dimensionless?
// If MULTIPLIER is actually a price {USD/TOKEN}, this formula is WRONG
// If DIVISOR is actually an amount {TOKEN}, this formula is WRONG

// Always verify what constants represent
```

### Trap 2: Hidden Dimension in Helper Function

```solidity
// Is this correct?
uint256 normalized = normalize(amount);

// Question: What dimension does normalize() return?
// - Does it change {TOKEN_A} to {TOKEN_B}?
// - Does it convert to {USD}?
// - Does it change scale but not dimension?

// MUST trace into the helper function
```

### Trap 3: Chained Operations Hiding Dimension Changes

```solidity
// Is this correct?
uint256 final = step1(step2(step3(input)));

// MUST trace dimensions through each step
// Don't assume the chain is correct because each function "looks right"

// Trace:
//   input           : {A}
//   step3(input)    : {?} - determine from step3's implementation
//   step2(step3...) : {?} - determine from step2's implementation
//   step1(step2...) : {?} - determine from step1's implementation
//   final           : expected {?}
```

### Trap 4: Scale Confused with Dimension

```solidity
// Common mistake:
uint256 price = oracle.getPrice();     // D8{USD/TOKEN}
uint256 value = amount * price / 1e18; // WRONG! Should be 1e8

// Scale is PART of dimensional correctness
// D18{TOKEN} * D8{USD/TOKEN} / 1e18 = D8{USD}  ← wrong scale
// D18{TOKEN} * D8{USD/TOKEN} / 1e8  = D18{USD} ← correct scale
```

### Trap 5: Decimals vs Amounts (Common Real Bug)

```solidity
// Extremely common bug pattern:
uint256 decimals = IERC20(token).decimals();  // Returns 18, dimension is {1}
uint256 amount = vault.convertToAssets(decimals);  // WRONG! Expects {SHARE}

// decimals is a COUNT, not a token amount
// It has dimension {1}, not {TOKEN} or {SHARE}
```

**Real-world example:**
```solidity
// BUGGY CODE (simplified from real audit)
function price(address _asset) external view returns (uint256 latestAnswer) {
    address underlying = IERC4626(_asset).asset();
    (latestAnswer, ) = IOracle(msg.sender).getPrice(underlying);
    uint256 tokenDecimals = IERC20Metadata(underlying).decimals();
    uint256 pricePerFullShare = IERC4626(_asset).convertToAssets(tokenDecimals);
    latestAnswer = latestAnswer * pricePerFullShare / tokenDecimals;
}
```

**Dimensional analysis catches this:**
```
Step 1: What does convertToAssets expect?
  According to ERC-4626: input is {SHARE}, output is {ASSET}

Step 2: What is tokenDecimals?
  It's the NUMBER of decimals (e.g., 18), dimension is {1}
  NOT a token amount!

Step 3: Trace the call
  convertToAssets(tokenDecimals)
  convertToAssets({1})  // WRONG! Expects {SHARE}

  This passes a dimensionless number where a share amount is expected!

BUG: decimals (a count, {1}) was passed to a function expecting assets ({SHARE})
```

### Trap 6: Same Name, Different Tokens

```solidity
// Is this correct?
uint256 total = totalSupplyA + totalSupplyB;

// If A and B are different tokens:
//   {TOKEN_A} + {TOKEN_B} = ??? (INVALID)

// Same-named variables for different tokens can't be added
```

---

## Detection Strategies

### Static Analysis

1. **Parse annotations** - Extract all dimensional comments
2. **Build dimension graph** - Map variable → dimension
3. **Trace arithmetic** - Apply algebra rules
4. **Check assignments** - LHS must match RHS dimension
5. **Check function boundaries** - Args match params, returns match declarations

### Code Patterns to Flag

```solidity
// Flag: Multiplication without mulDiv
a * b                           // Needs dimension check

// Flag: Direct oracle assignment
price = oracle.latestAnswer()   // Check precision match

// Flag: Addition of different variables
total = valueA + valueB         // Verify same dimension

// Flag: Return in conditional
if (x) return a; else return b; // Verify a and b same dimension

// Flag: Scaling literals
value * 1e9                     // Verify direction correct
value / 1e18                    // Verify scaling appropriate
```

### Human Review Triggers

- Cross-contract calls (external assumptions)
- Complex multi-step calculations
- Non-standard token decimals (not 18)
- Custom oracle implementations
- Protocol-specific units

## False Positive Avoidance

### Acceptable Patterns

```solidity
// Intentional dimensionless arithmetic
uint256 doubled = amount * 2;       // {tok} * {1} = {tok}

// Loop bounds
for (uint256 i = 0; i < length; i++)  // {1}

// Explicit documented conversion
// Intentionally converting D27 to D18 with precision loss
uint256 approxPrice = precisePrice / 1e9;

// Test contracts
contract MockOracle { ... }         // Ignore test code
```

### Context Clues

- Check for comments explaining intent
- Check for test file paths
- Check for "mock" or "test" in names
- Check for explicit precision documentation
