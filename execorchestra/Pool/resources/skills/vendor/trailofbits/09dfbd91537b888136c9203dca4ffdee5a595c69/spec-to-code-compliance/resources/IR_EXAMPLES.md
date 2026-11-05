# Intermediate Representation Examples

The following examples demonstrate the complete IR workflow using realistic DEX swap patterns.

---

## Example 1: Spec-IR Record

**Scenario:** Extracting a security requirement from a DEX protocol whitepaper.

```yaml
id: SPEC-001
spec_excerpt: "All swaps MUST enforce maximum slippage of 1% to protect users from sandwich attacks"
source_section: "Whitepaper §4.1 - Trading Mechanism & User Protection"
source_document: "dex-protocol-whitepaper-v3.pdf"
semantic_type: invariant
normalized_form:
  type: constraint
  entity: swap_transaction
  operation: token_exchange
  condition: "abs((actual_output - expected_output) / expected_output) <= 0.01"
  enforcement: MUST (mandatory)
  rationale: "sandwich_attack_prevention"
confidence: 1.0
notes: "Slippage measured as percentage deviation from expected output at transaction submission time"
```

**What this shows:**
- Extraction of trading protection requirement with full traceability
- Normalized form makes slippage calculation explicit and machine-verifiable
- High confidence (1.0) because requirement is stated explicitly with specific percentage
- Notes clarify measurement methodology

---

## Example 2: Code-IR Record

**Scenario:** Analyzing the `swap()` function in a DEX router contract.

```yaml
id: CODE-001
file: "contracts/Router.sol"
function: "swap(address tokenIn, address tokenOut, uint256 amountIn, uint256 minAmountOut, uint256 deadline)"
lines: 89-135
visibility: external
modifiers: [nonReentrant, ensure(deadline)]

behavior:
  preconditions:
    - condition: "block.timestamp <= deadline"
      line: 90
      enforcement: modifier (ensure)
      purpose: "prevent stale transactions"
    - condition: "amountIn > 0"
      line: 92
      enforcement: require
    - condition: "minAmountOut > 0"
      line: 93
      enforcement: require
    - condition: "tokenIn != tokenOut"
      line: 94
      enforcement: require

  state_reads:
    - variable: "pairs[tokenIn][tokenOut]"
      line: 98
      purpose: "get liquidity pool address"
    - variable: "reserves[pair]"
      line: 102
      purpose: "get current pool reserves"
    - variable: "feeRate"
      line: 108
      purpose: "calculate trading fee"

  state_writes:
    - variable: "reserves[pair].reserve0"
      line: 125
      operation: "update after swap"
    - variable: "reserves[pair].reserve1"
      line: 126
      operation: "update after swap"

  computations:
    - operation: "amountInWithFee = amountIn * 997"
      line: 108
      purpose: "apply 0.3% fee (997/1000)"
    - operation: "amountOut = (amountInWithFee * reserveOut) / (reserveIn * 1000 + amountInWithFee)"
      line: 110-111
      purpose: "constant product formula (x * y = k)"
    - operation: "slippageCheck = amountOut >= minAmountOut"
      line: 115
      purpose: "enforce user-specified minimum output"

  external_calls:
    - target: "IERC20(tokenIn).transferFrom(msg.sender, pair, amountIn)"
      line: 118
      type: "ERC20 transfer"
      return_handling: "require success"
    - target: "IERC20(tokenOut).transfer(msg.sender, amountOut)"
      line: 122
      type: "ERC20 transfer"
      return_handling: "require success"

  events:
    - name: "Swap"
      line: 130
      parameters: "msg.sender, tokenIn, tokenOut, amountIn, amountOut"

  postconditions:
    - "amountOut >= minAmountOut (slippage protection enforced)"
    - "reserves updated to maintain K=xy invariant"
    - "tokenIn transferred from user to pool"
    - "tokenOut transferred from pool to user"

invariants_enforced:
  - "slippage_protection: amountOut >= minAmountOut (line 115)"
  - "constant_product: reserveIn * reserveOut >= k_before (line 125-126)"
  - "fee_application: effective_rate = 0.3% (line 108)"
```

**What this shows:**
- Complete DEX swap function analysis with line-level precision
- Captures AMM constant product formula and fee mechanics
- Documents slippage protection enforcement at line 115
- Shows state transitions (reserve updates) and external interactions
- All claims reference specific line numbers for traceability

---

## Example 3: Alignment Record (Positive Case)

**Scenario:** Verifying that the swap function correctly implements the 0.3% fee requirement.

```yaml
id: ALIGN-001
spec_ref: SPEC-002
code_ref: CODE-001

spec_claim: "Protocol MUST charge exactly 0.3% fee on all swaps"
spec_source: "Whitepaper §4.2 - Fee Structure"

code_behavior: "amountInWithFee = amountIn * 997 (line 108), effective fee = (1000-997)/1000 = 0.3%"
code_location: "Router.sol:L108"

match_type: full_match
confidence: 1.0

reasoning: |
  Spec requires: 0.3% fee on all swaps
  Code implements: amountIn * 997 / 1000

  Mathematical verification:
  - Fee deduction: 1000 - 997 = 3
  - Fee percentage: 3 / 1000 = 0.003 = 0.3% ✓

  The code uses numerator 997 instead of explicit fee subtraction,
  but this is mathematically equivalent and gas-optimized.

  Enforcement: Fee is applied before price calculation (line 108-111),
  ensuring it affects the swap output. Cannot be bypassed.

evidence:
  spec_quote: "The protocol charges a fixed 0.3% fee on the input amount for every swap transaction"
  spec_location: "Whitepaper §4.2, page 8, paragraph 1"
  code_quote: "uint256 amountInWithFee = amountIn * 997; // 0.3% fee: (1000-997)/1000"
  code_location: "Router.sol:L108"

  verification_steps:
    - "Checked numerator 997 is used consistently"
    - "Verified denominator 1000 matches in formula at L110-111"
    - "Confirmed fee applies to all swap paths (no conditional logic)"
    - "Validated fee is not configurable (hardcoded = guaranteed)"

ambiguity_notes: null
```

**What this shows:**
- Successful alignment between spec requirement and code implementation
- Mathematical proof that 997/1000 = 0.3% fee
- Reasoning explains WHY implementation is correct (gas optimization via numerator)
- Evidence provides exact quotes and line numbers
- High confidence (1.0) due to clear mathematical equivalence

---

## Example 4: Divergence Finding (Critical Issue)

**Scenario:** Identifying that the critical slippage protection requirement is completely missing.

```yaml
id: DIV-001
severity: CRITICAL
title: "Missing slippage protection enables unlimited sandwich attacks"

spec_claim:
  excerpt: "All swaps MUST enforce maximum slippage of 1% to protect users from sandwich attacks"
  source: "Whitepaper §4.1 - Trading Mechanism & User Protection"
  source_location: "Page 7, paragraph 3"
  semantic_type: security_constraint
  enforcement_level: MUST (mandatory)

code_finding:
  file: "contracts/RouterV1.sol"
  function: "swap(address tokenIn, address tokenOut, uint256 amountIn)"
  lines: 45-78
  observation: "Function signature lacks minAmountOut parameter; no slippage validation exists"

match_type: missing_in_code
confidence: 1.0

reasoning: |
  Specification Analysis:
  - Spec explicitly requires: "MUST enforce maximum slippage of 1%"
  - Requirement scope: "All swaps" (no exceptions)
  - Purpose stated: "protect users from sandwich attacks"

  Code Analysis:
  - Function signature: swap(tokenIn, tokenOut, amountIn)
  - Missing parameter: minAmountOut (required for slippage check)
  - Line-by-line review of function body (L45-L78):
    * L50-55: Price calculation from reserves
    * L58-60: Fee deduction (0.3%)
    * L62-65: Output amount calculation
    * L68: Transfer tokenIn from user
    * L72: Transfer tokenOut to user
    * L75: Emit Swap event
  - NO slippage validation found anywhere in function

  Gap: Spec requires slippage protection → Code provides zero protection

  Additional verification:
  - Searched entire RouterV1.sol for "slippage", "minAmount", "minOutput": 0 results
  - Checked if validation exists in called functions: None found
  - Verified no modifiers perform slippage check: Confirmed absent

evidence:
  spec_evidence:
    quote: "To protect users from front-running and sandwich attacks, all swap operations MUST enforce a maximum slippage of 1% between the expected and actual output amounts"
    location: "Whitepaper §4.1, page 7, paragraph 3"
    emphasis: "MUST" indicates mandatory requirement

  code_evidence:
    function_signature: "function swap(address tokenIn, address tokenOut, uint256 amountIn) external"
    signature_location: "RouterV1.sol:L45"
    missing_parameter: "uint256 minAmountOut"

    function_body_summary: |
      L50: uint256 amountOut = calculateSwapOutput(tokenIn, tokenOut, amountIn);
      L68: IERC20(tokenIn).transferFrom(msg.sender, pair, amountIn);
      L72: IERC20(tokenOut).transfer(msg.sender, amountOut);

      CRITICAL ISSUE: No validation that amountOut meets user expectations

    search_results:
      - pattern: "minAmountOut" → 0 occurrences in RouterV1.sol
      - pattern: "slippage" → 0 occurrences in RouterV1.sol
      - pattern: "require.*amountOut" → 0 occurrences in RouterV1.sol
      - pattern: "amountOut >=" → 0 occurrences in RouterV1.sol

exploitability: |
  Attack Vector: Classic Sandwich Attack

  Prerequisites:
  - Attacker monitors public mempool for pending swap transactions
  - Attacker has capital to move market price (typically 10-50x target trade size)
  - Target trade is on-chain (not private mempool)

  Attack Sequence:

  1. Detection Phase
     - Victim submits swap: 100 ETH → USDC
     - Expected output at current price: 200,000 USDC (price = $2,000/ETH)
     - Transaction appears in mempool with no slippage protection

  2. Front-Run Transaction
     - Attacker submits swap: 500 ETH → USDC (higher gas to execute first)
     - Large buy moves price: $2,000 → $2,100 (+5%)
     - Pool reserves now imbalanced

  3. Victim Transaction Executes
     - Victim's 100 ETH swap executes at manipulated price
     - Actual output: 195,122 USDC (effective price $1,951/ETH)
     - Victim loses: 4,878 USDC vs expected 200,000
     - Loss percentage: 2.4% of trade value
     - NO PROTECTION: Transaction succeeds despite 2.4% slippage (exceeds 1% spec limit)

  4. Back-Run Transaction
     - Attacker sells USDC → ETH at inflated price
     - Profits from price impact: ~$4,500
     - Price returns toward equilibrium

  Economic Analysis:
  - Victim trade size: $200,000
  - Attacker cost: Gas fees (~$50-100)
  - Attacker profit: ~$4,500 (net ~$4,400)
  - Victim loss: $4,878 (2.4% slippage)
  - Attack ROI: 4400% in single block

  Impact Scale:
  - Per transaction: $500 - $10,000 extractable (depending on trade size)
  - Daily volume: $10M → potential $100K-500K daily extraction
  - Unlimited because: No slippage check = no upper bound on extraction

  Real-World Precedent:
  - SushiSwap (2020): Suffered sandwich attacks before slippage protection
  - Average loss per victim: 1-5% of trade value
  - Specification exists specifically to prevent this attack class

remediation:
  immediate_fix: |
    Add minAmountOut parameter and enforce slippage protection:

    ```solidity
    function swap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,  // NEW: User-specified minimum output
        uint256 deadline        // NEW: Prevent stale transactions
    ) external ensure(deadline) nonReentrant {
        require(amountIn > 0, "Invalid input amount");
        require(minAmountOut > 0, "Invalid minimum output");  // NEW

        // Existing price calculation
        uint256 amountOut = calculateSwapOutput(tokenIn, tokenOut, amountIn);

        // NEW: Enforce slippage protection
        require(amountOut >= minAmountOut, "Slippage exceeded");

        // Rest of swap logic...
    }
    ```

    This allows users to specify maximum acceptable slippage:
    - User calculates expected output: 200,000 USDC
    - User sets minAmountOut: 198,000 USDC (1% slippage tolerance)
    - Sandwich attack moves price 2.4% → transaction reverts
    - User protected from excessive value extraction

  long_term_improvements: |
    1. Add helper function for slippage calculation:
       ```solidity
       function calculateMinOutput(
           uint256 expectedOutput,
           uint256 slippageBps  // basis points, e.g., 100 = 1%
       ) public pure returns (uint256) {
           return expectedOutput * (10000 - slippageBps) / 10000;
       }
       ```

    2. Implement deadline parameter (as shown in immediate fix)
       - Prevents stale transactions from executing at unexpected prices
       - Standard in Uniswap V2/V3

    3. Add price impact warnings in UI:
       - Show estimated price impact before transaction
       - Warn if impact exceeds 1% (spec threshold)
       - Suggest splitting large trades

    4. Consider TWAP (Time-Weighted Average Price) validation:
       - Compare spot price vs 30-min TWAP
       - Reject if deviation exceeds threshold
       - Prevents oracle manipulation attacks

    5. Add events for slippage monitoring:
       ```solidity
       event SlippageApplied(
           address indexed user,
           uint256 expectedOutput,
           uint256 actualOutput,
           uint256 slippageBps
       );
       ```

  testing_requirements: |
    1. Unit test: Swap with 0.5% slippage succeeds
    2. Unit test: Swap with 1.5% slippage reverts
    3. Integration test: Simulate sandwich attack, verify protection
    4. Fuzz test: Random minAmountOut values, verify correct revert behavior
    5. Mainnet fork test: Replay historical sandwich attacks, verify prevention

  breaking_changes: |
    YES - This is a breaking change to the swap() function signature.

    Migration path:
    1. Deploy RouterV2 with new signature
    2. Update frontend to calculate and pass minAmountOut
    3. Deprecate RouterV1 after 30-day migration period
    4. Add wrapper function in RouterV1 for backward compatibility:
       ```solidity
       function swapLegacy(address tokenIn, address tokenOut, uint256 amountIn) external {
           uint256 expectedOutput = getExpectedOutput(tokenIn, tokenOut, amountIn);
           uint256 minOutput = expectedOutput * 99 / 100;  // 1% default slippage
           swap(tokenIn, tokenOut, amountIn, minOutput, block.timestamp + 300);
       }
       ```

  specification_update: |
    If slippage protection is intentionally omitted (NOT recommended):

    Update whitepaper §4.1 to:
    "Swaps execute at current market price without slippage protection.
    Users are responsible for sandwich attack mitigation via:
    - Private transaction channels (Flashbots, MEV-Blocker)
    - Off-chain price monitoring and transaction cancellation
    - External slippage calculation and manual validation

    WARNING: On-chain swaps are vulnerable to MEV extraction."
```

**What this shows:**
- Complete divergence finding with CRITICAL severity
- Evidence-based: Shows exhaustive search for slippage protection (0 results)
- Detailed exploit scenario with concrete numbers ($200k trade → $4,878 loss)
- Economic impact quantification (ROI, daily volume, extraction potential)
- Comprehensive remediation with code examples, testing requirements, migration path
- Distinguishes between fixing code vs updating spec (if intentional)
