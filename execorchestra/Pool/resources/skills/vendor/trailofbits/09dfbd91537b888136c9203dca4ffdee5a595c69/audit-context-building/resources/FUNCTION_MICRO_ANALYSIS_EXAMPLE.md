# Function Micro-Analysis Example

This example demonstrates a complete micro-analysis following the Per-Function Microstructure Checklist.

---

## Target: `swap(address tokenIn, address tokenOut, uint256 amountIn, uint256 minAmountOut, uint256 deadline)` in Router.sol

**Purpose:**
Enables users to swap one token for another through a liquidity pool. Core trading operation in a DEX that:
- Calculates output amount using constant product formula (x * y = k)
- Deducts 0.3% protocol fee from input amount
- Enforces user-specified slippage protection
- Updates pool reserves to maintain AMM invariant
- Prevents stale transactions via deadline check

This is a critical financial primitive affecting pool solvency, user fund safety, and protocol fee collection.

---

**Inputs & Assumptions:**

*Parameters:*
- `tokenIn` (address): Source token to swap from. Assumed untrusted (could be malicious ERC20).
- `tokenOut` (address): Destination token to receive. Assumed untrusted.
- `amountIn` (uint256): Amount of tokenIn to swap. User-specified, untrusted input.
- `minAmountOut` (uint256): Minimum acceptable output. User-specified slippage tolerance.
- `deadline` (uint256): Unix timestamp. Transaction must execute before this or revert.

*Implicit Inputs:*
- `msg.sender`: Transaction initiator. Assumed to have approved Router to spend amountIn of tokenIn.
- `pairs[tokenIn][tokenOut]`: Storage mapping to pool address. Assumed populated during pool creation.
- `reserves[pair]`: Pool's current token reserves. Assumed synchronized with actual pool balances.
- `block.timestamp`: Current block time. Assumed honest (no validator manipulation considered here).

*Preconditions:*
- Pool exists for tokenIn/tokenOut pair (pairs[tokenIn][tokenOut] != address(0))
- msg.sender has approved Router for at least amountIn of tokenIn
- msg.sender balance of tokenIn >= amountIn
- Pool has sufficient liquidity to output at least minAmountOut
- block.timestamp <= deadline

*Trust Assumptions:*
- Pool contract correctly maintains reserves
- ERC20 tokens follow standard behavior (return true on success, revert on failure)
- No reentrancy from tokenIn/tokenOut during transfers (or handled by nonReentrant modifier)

---

**Outputs & Effects:**

*Returns:*
- Implicit: amountOut (not returned, but emitted in event)

*State Writes:*
- `reserves[pair].reserve0` and `reserves[pair].reserve1`: Updated to reflect post-swap balances
- Pool token balances: Physical token transfers change actual balances

*External Interactions:*
- `IERC20(tokenIn).transferFrom(msg.sender, pair, amountIn)`: Pulls tokenIn from user to pool
- `IERC20(tokenOut).transfer(msg.sender, amountOut)`: Sends tokenOut from pool to user

*Events Emitted:*
- `Swap(msg.sender, tokenIn, tokenOut, amountIn, amountOut, block.timestamp)`

*Postconditions:*
- `amountOut >= minAmountOut` (slippage protection enforced)
- Pool reserves updated: `reserve0 * reserve1 >= k_before` (constant product maintained with fee)
- User received exactly amountOut of tokenOut
- Pool received exactly amountIn of tokenIn
- Fee collected: `amountIn * 0.003` remains in pool as liquidity

---

**Block-by-Block Analysis:**

```solidity
// L90: Deadline validation (modifier: ensure(deadline))
modifier ensure(uint256 deadline) {
    require(block.timestamp <= deadline, "Expired");
    _;
}
```
- **What:** Checks transaction hasn't expired based on user-provided deadline
- **Why here:** First line of defense; fail fast before any state reads or computation
- **Assumption:** `block.timestamp` is sufficiently honest (no 900-second manipulation considered)
- **Depends on:** User setting reasonable deadline (e.g., block.timestamp + 300 seconds)
- **First Principles:** Time-sensitive operations need expiration to prevent stale execution at unexpected prices
- **5 Whys:**
  - Why check deadline? → Prevent stale transactions
  - Why are stale transactions bad? → Price may have moved significantly
  - Why not just use slippage protection? → Slippage doesn't prevent execution hours later
  - Why does timing matter? → Market conditions change, user intent expires
  - Why user-provided vs fixed? → User decides their time tolerance based on urgency

---

```solidity
// L92-94: Input validation
require(amountIn > 0, "Invalid input amount");
require(minAmountOut > 0, "Invalid minimum output");
require(tokenIn != tokenOut, "Identical tokens");
```
- **What:** Validates basic input sanity (non-zero amounts, different tokens)
- **Why here:** Second line of defense; cheap checks before expensive operations
- **Assumption:** Zero amounts indicate user error, not intentional probe
- **Invariant established:** `amountIn > 0 && minAmountOut > 0 && tokenIn != tokenOut`
- **First Principles:** Fail fast on invalid input before consuming gas on computation/storage
- **5 Hows:**
  - How to ensure valid swap? → Check inputs meet minimum requirements
  - How to check minimum requirements? → Test amounts > 0 and tokens differ
  - How to handle violations? → Revert with descriptive error
  - How to order checks? → Cheapest first (inequality checks before storage reads)
  - How to communicate failure? → Require statements with clear messages

---

```solidity
// L98-99: Pool resolution
address pair = pairs[tokenIn][tokenOut];
require(pair != address(0), "Pool does not exist");
```
- **What:** Looks up liquidity pool address for token pair, validates existence
- **Why here:** Must identify pool before reading reserves or executing transfers
- **Assumption:** `pairs` mapping is correctly populated during pool creation; no race conditions
- **Depends on:** Factory having called createPair(tokenIn, tokenOut) previously
- **Invariant established:** `pair != 0x0` (valid pool address exists)
- **Risk:** If pairs mapping is corrupted or pool address is incorrect, funds could be sent to wrong address

---

```solidity
// L102-103: Reserve reads
(uint112 reserveIn, uint112 reserveOut) = getReserves(pair, tokenIn, tokenOut);
require(reserveIn > 0 && reserveOut > 0, "Insufficient liquidity");
```
- **What:** Reads current pool reserves for tokenIn and tokenOut, validates pool has liquidity
- **Why here:** Need current reserves to calculate output amount; must confirm pool is operational
- **Assumption:** `reserves[pair]` storage is synchronized with actual pool token balances
- **Invariant established:** `reserveIn > 0 && reserveOut > 0` (pool is liquid)
- **Depends on:** Sync mechanism keeping reserves accurate (called after transfers/swaps)
- **5 Whys:**
  - Why read reserves? → Need current pool state for price calculation
  - Why must reserves be > 0? → Division by zero in formula if empty
  - Why check liquidity here? → Cheaper to fail now than after transferFrom
  - Why not just try the swap? → Better UX with specific error message
  - Why trust reserves storage? → Alternative is querying balances (expensive)

---

```solidity
// L108-109: Fee application
uint256 amountInWithFee = amountIn * 997;
uint256 numerator = amountInWithFee * reserveOut;
```
- **What:** Applies 0.3% protocol fee by multiplying amountIn by 997 (instead of deducting 3)
- **Why here:** Fee must be applied before price calculation to affect output amount
- **Assumption:** 997/1000 = 0.997 = (1 - 0.003) represents 0.3% fee deduction
- **Invariant maintained:** `amountInWithFee = amountIn * 0.997` (3/1000 fee taken)
- **First Principles:** Fees modify effective input, reducing output proportionally
- **5 Whys:**
  - Why multiply by 997? → Gas optimization: avoids separate subtraction step
  - Why not amountIn * 0.997? → Solidity doesn't support floating point
  - Why 0.3% fee? → Protocol parameter (Uniswap V2 standard, commonly copied)
  - Why apply before calculation? → Fee reduces input amount, must affect price
  - Why not apply after? → Would incorrectly calculate output at full amountIn

---

```solidity
// L110-111: Output calculation (constant product formula)
uint256 denominator = (reserveIn * 1000) + amountInWithFee;
uint256 amountOut = numerator / denominator;
```
- **What:** Calculates output amount using AMM constant product formula: `Δy = (x * Δx_fee) / (y + Δx_fee)`
- **Why here:** After fee application; core pricing logic of the AMM
- **Assumption:** `k = reserveIn * reserveOut` is the invariant to maintain (with fee adding to k)
- **Invariant formula:** `(reserveIn + amountIn) * (reserveOut - amountOut) >= reserveIn * reserveOut`
- **First Principles:** Constant product AMM maintains `x * y = k` (with fee slightly increasing k)
- **5 Whys:**
  - Why this formula? → Constant product market maker (x * y = k)
  - Why not linear pricing? → Would drain pool at constant price (exploitable)
  - Why multiply reserveIn by 1000? → Match denominator scale with numerator (997 * 1000)
  - Why divide? → Solving for Δy in: (x + Δx_fee) * (y - Δy) = k
  - Why this maintains k? → New product = (reserveIn + amountIn*0.997) * (reserveOut - amountOut) ≈ k * 1.003
- **Mathematical verification:**
  - Given: `k = reserveIn * reserveOut`
  - New reserves: `reserveIn' = reserveIn + amountIn`, `reserveOut' = reserveOut - amountOut`
  - With fee: `amountInWithFee = amountIn * 0.997`
  - Solving `(reserveIn + amountIn) * (reserveOut - amountOut) = k`:
    - `reserveOut - amountOut = k / (reserveIn + amountIn)`
    - `amountOut = reserveOut - k / (reserveIn + amountIn)`
    - Substituting and simplifying yields the formula above

---

```solidity
// L115: Slippage protection enforcement
require(amountOut >= minAmountOut, "Slippage exceeded");
```
- **What:** Validates calculated output meets user's minimum acceptable amount
- **Why here:** After calculation, before any state changes or transfers (fail fast if insufficient)
- **Assumption:** User calculated minAmountOut correctly based on acceptable slippage tolerance
- **Invariant enforced:** `amountOut >= minAmountOut` (user-defined slippage limit)
- **First Principles:** User must explicitly consent to price via slippage tolerance; prevents sandwich attacks
- **5 Whys:**
  - Why check minAmountOut? → Protect user from excessive slippage
  - Why is slippage protection critical? → Prevents sandwich attacks and MEV extraction
  - Why user-specified? → Different users have different risk tolerances
  - Why fail here vs warn? → Financial safety: user should not receive less than intended
  - Why before transfers? → Cheaper to revert now than after expensive external calls
- **Attack scenario prevented:**
  - Attacker front-runs with large buy → price increases
  - Victim's swap would execute at worse price
  - This check causes victim's transaction to revert instead
  - Attacker cannot profit from sandwich

---

```solidity
// L118: Input token transfer (pull pattern)
IERC20(tokenIn).transferFrom(msg.sender, pair, amountIn);
```
- **What:** Pulls tokenIn from user to liquidity pool
- **Why here:** After all validations pass; begins state-changing operations (point of no return)
- **Assumption:** User has approved Router for at least amountIn; tokenIn is standard ERC20
- **Depends on:** Prior approval: `tokenIn.approve(router, amountIn)` called by user
- **Risk considerations:**
  - If tokenIn is malicious: could revert (DoS), consume excessive gas, or attempt reentrancy
  - If tokenIn has transfer fee: actual amount received < amountIn (breaks invariant)
  - If tokenIn is pausable: could revert if paused
  - Reentrancy: If tokenIn has callback, attacker could call Router again (mitigated by nonReentrant modifier)
- **First Principles:** Pull pattern (transferFrom) is safer than users sending first (push) - Router controls timing
- **5 Hows:**
  - How to get tokenIn? → Pull from user via transferFrom
  - How to ensure Router can pull? → User must have approved Router
  - How to specify destination? → Send directly to pair (gas optimization: no router intermediate storage)
  - How to handle failures? → transferFrom reverts on failure (ERC20 standard)
  - How to prevent reentrancy? → nonReentrant modifier (assumed present)

---

```solidity
// L122: Output token transfer (push pattern)
IERC20(tokenOut).transfer(msg.sender, amountOut);
```
- **What:** Sends calculated amountOut of tokenOut from pool to user
- **Why here:** After input transfer succeeds; completes the swap atomically
- **Assumption:** Pool has at least amountOut of tokenOut; tokenOut is standard ERC20
- **Invariant maintained:** User receives exact amountOut (no more, no less)
- **Risk considerations:**
  - If tokenOut is malicious: could revert (DoS), but user selected this token pair
  - If tokenOut has transfer hook: could attempt reentrancy (mitigated by nonReentrant)
  - If transfer fails: entire transaction reverts (atomic swap)
- **CEI pattern:** Not strictly followed (Check-Effects-Interactions) - both transfers are interactions
  - Typically Effects (reserve update) should precede Interactions (transfers)
  - Here, transfers happen before reserve update (see next block)
  - Justification: nonReentrant modifier prevents exploitation
- **5 Whys:**
  - Why transfer to msg.sender? → User initiated swap, they receive output
  - Why not to an arbitrary recipient? → Simplicity; extensions can add recipient parameter
  - Why this amount exactly? → amountOut calculated from constant product formula
  - Why after input transfer? → Ensures atomicity: both succeed or both fail
  - Why trust pool has balance? → Pool's job to maintain reserves; if insufficient, transfer reverts

---

```solidity
// L125-126: Reserve synchronization
reserves[pair].reserve0 = uint112(reserveIn + amountIn);
reserves[pair].reserve1 = uint112(reserveOut - amountOut);
```
- **What:** Updates stored reserves to reflect post-swap balances
- **Why here:** After transfers complete; brings storage in sync with actual balances
- **Assumption:** No other operations have modified pool balances since reserves were read
- **Invariant maintained:** `reserve0 * reserve1 >= k_before * 1.003` (constant product + fee)
- **Casting risk:** `uint112` casting could truncate if reserves exceed 2^112 - 1 (≈ 5.2e33)
  - For most tokens with 18 decimals: limit is ~5.2e15 tokens
  - Overflow protection: require reserves fit in uint112, else revert
- **5 Whys:**
  - Why update reserves? → Storage must match actual balances for next swap
  - Why after transfers? → Need to know final state before recording
  - Why not query balances? → Gas optimization: storage update cheaper than CALL + BALANCE
  - Why uint112? → Pack two reserves in one storage slot (256 bits = 2 * 112 + 32 for timestamp)
  - Why this formula? → reserveIn increased by amountIn, reserveOut decreased by amountOut
- **Invariant verification:**
  - Before: `k_before = reserveIn * reserveOut`
  - After: `k_after = (reserveIn + amountIn) * (reserveOut - amountOut)`
  - With 0.3% fee: `k_after ≈ k_before * 1.003` (fee adds permanent liquidity)

---

```solidity
// L130: Event emission
emit Swap(msg.sender, tokenIn, tokenOut, amountIn, amountOut, block.timestamp);
```
- **What:** Emits event logging swap details for off-chain indexing
- **Why here:** After all state changes finalized; last operation before return
- **Assumption:** Event watchers (subgraphs, dex aggregators) rely on this for tracking trades
- **Data included:**
  - `msg.sender`: Who initiated swap (for user trade history)
  - `tokenIn/tokenOut`: Which pair was traded
  - `amountIn/amountOut`: Exact amounts for price tracking
  - `block.timestamp`: When trade occurred (for TWAP calculations, analytics)
- **First Principles:** Events are write-only log for off-chain systems; don't affect on-chain state
- **5 Hows:**
  - How to notify off-chain? → Emit event (logs are cheaper than storage)
  - How to structure event? → Include all relevant swap parameters
  - How do indexers use this? → Build trade history, calculate volume, track prices
  - How to ensure consistency? → Emit after state finalized (can't be front-run)
  - How to query later? → Blockchain logs filtered by event signature + contract address

---

**Cross-Function Dependencies:**

*Internal Calls:*
- `getReserves(pair, tokenIn, tokenOut)`: Helper to read and order reserves based on token addresses
  - Depends on: `reserves[pair]` storage being synchronized
  - Returns: (reserveIn, reserveOut) in correct order for tokenIn/tokenOut

*External Calls (Outbound):*
- `IERC20(tokenIn).transferFrom(msg.sender, pair, amountIn)`: ERC20 standard call
  - Assumes: tokenIn implements ERC20, user has approved Router
  - Reentrancy risk: If tokenIn is malicious, could callback
  - Failure: Reverts entire transaction
- `IERC20(tokenOut).transfer(msg.sender, amountOut)`: ERC20 standard call
  - Assumes: Pool has sufficient tokenOut balance
  - Reentrancy risk: If tokenOut has hooks
  - Failure: Reverts entire transaction

*Called By:*
- Users directly (external call)
- Aggregators/routers (external call)
- Multi-hop swap functions (internal call from same contract)

*Shares State With:*
- `addLiquidity()`: Modifies same reserves[pair], must maintain k invariant
- `removeLiquidity()`: Modifies same reserves[pair]
- `sync()`: Emergency function to force reserves sync with balances
- `skim()`: Removes excess tokens beyond reserves

*Invariant Coupling:*
- **Global invariant:** `sum(all reserves[pair].reserve0 for all pairs) <= sum(all token balances in pools)`
- **Per-pool invariant:** `reserves[pair].reserve0 * reserves[pair].reserve1 >= k_initial * (1.003^n)` where n = number of swaps
  - Each swap increases k by 0.3% due to fee
- **Reentrancy protection:** `nonReentrant` modifier ensures no cross-function reentrancy
  - swap() cannot be re-entered while executing
  - addLiquidity/removeLiquidity also cannot execute during swap

*Assumptions Propagated to Callers:*
- Caller must have approved Router to spend amountIn of tokenIn
- Caller must set reasonable deadline (e.g., block.timestamp + 300 seconds)
- Caller must calculate minAmountOut based on acceptable slippage (e.g., expectedOutput * 0.99 for 1%)
- Caller assumes pair exists (or will handle "Pool does not exist" revert)
