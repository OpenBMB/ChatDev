# Step 2: Annotate the Codebase

After defining dimensions (Step 1), add annotations to all numeric values in the code.

> **Note:** Examples below use Solidity syntax. For other languages, adapt the comment syntax (e.g., `//` in Rust, `#` in Python, `//` or `/** */` in TypeScript) while keeping the same dimensional annotation format.

---

## Comment Placement Patterns

### Variable Declarations

```solidity
// Inline (preferred for brevity)
uint256 public totalAssets;  // D18{UNDERLYING}

// Above (for longer descriptions)
/// D18{UNDERLYING} Total assets under management, excluding pending withdrawals
uint256 public totalAssets;
```

### Function Parameters (NatSpec)

```solidity
// NatSpec (preferred)
/// @param assets D18{UNDERLYING} Amount to deposit
/// @param receiver Address receiving shares
/// @return shares D18{SHARE} Shares minted
function deposit(uint256 assets, address receiver) external returns (uint256 shares);

// Inline (acceptable for simple cases)
function deposit(
    uint256 assets,   // D18{UNDERLYING}
    address receiver
) external returns (uint256 shares);  // D18{SHARE}
```

### Struct Fields

```solidity
struct Position {
    uint256 collateral;    // D18{COLLATERAL} Collateral deposited
    uint256 debt;          // D18{DEBT} Amount borrowed
    uint256 lastUpdate;    // {s} Timestamp of last interest accrual
}
```

### Formula Verification Comments

```solidity
// Show dimensional algebra for non-trivial formulas
//
// shares = assets * totalSupply / totalAssets
// {SHARE} = {UNDERLYING} * {SHARE} / {UNDERLYING}
//         = {SHARE} ✓
//
shares = assets.mulDiv(totalSupply(), totalAssets());
```

---

## Annotating State Variables

For each state variable holding a numeric value:

1. Determine its dimension from the glossary
2. Determine its decimal scaling (D6, D8, D18, D27, etc.)
3. Add inline comment in format: `// D{scale}{dimension} Description`

### Examples

```solidity
// Storage variables
uint256 public totalDeposits;     // D18{UNDERLYING} Total tokens deposited
uint256 public totalShares;       // D18{VAULT} Total vault shares outstanding
uint256 public lastPriceUpdate;   // {s} Timestamp of last oracle update
uint256 public feeRate;           // D18{1} Fee as 18-decimal fraction (1e18 = 100%)
uint256 public accumulatedFees;   // D18{UNDERLYING} Protocol fees collected

// Mappings
mapping(address => uint256) public userShares;      // D18{VAULT} per user
mapping(address => uint256) public userDebt;        // D18{DEBT} per user
mapping(address => uint256) public lastActionTime;  // {s} per user
```

---

## Annotating Function Signatures

For each public/external function:

1. Add NatSpec with dimensions for all numeric parameters
2. Add dimensions for return values
3. Format: `@param name D{scale}{dimension} Description`

### Examples

```solidity
/// @notice Deposit assets and receive shares
/// @param assets D18{UNDERLYING} Amount of tokens to deposit
/// @param minShares D18{VAULT} Minimum shares to receive (slippage protection)
/// @return shares D18{VAULT} Actual shares minted
function deposit(uint256 assets, uint256 minShares) external returns (uint256 shares);

/// @notice Get current price from oracle
/// @return price D8{USD/UNDERLYING} Current asset price
function getPrice() external view returns (uint256 price);

/// @notice Calculate health factor for a position
/// @param collateralValue D18{USD} Total collateral value in USD
/// @param debtValue D18{USD} Total debt value in USD
/// @return healthFactor D18{1} Health factor (>1e18 is healthy)
function calculateHealthFactor(
    uint256 collateralValue,
    uint256 debtValue
) external pure returns (uint256 healthFactor);
```

---

## Full Annotated Examples

### ERC-4626 Vault

```solidity
/**
 * ═══════════════════════════════════════════════════════════
 * DIMENSIONAL GLOSSARY
 * ═══════════════════════════════════════════════════════════
 *
 * Base Dimensions:
 * - {UNDERLYING}  The underlying asset token
 * - {SHARE}       Vault share token
 * - {s}           Time in seconds
 * - {1}           Dimensionless
 *
 * Derived Dimensions:
 * - {SHARE/UNDERLYING}  Exchange rate (shares per asset)
 * - {UNDERLYING/SHARE}  Inverse exchange rate
 */

contract Vault is ERC4626 {
    uint256 public totalAssets;      // D{X}{UNDERLYING} where X = token decimals
    uint256 public totalSupply;      // D18{SHARE}
    uint256 public lastHarvestTime;  // {s} Timestamp of last yield harvest
    uint256 public performanceFee;   // D18{1} Fee rate (1e18 = 100%)

    /// @notice Deposit assets and receive shares
    /// @param assets D{X}{UNDERLYING} Amount to deposit
    /// @return shares D18{SHARE} Shares minted
    function deposit(uint256 assets) external returns (uint256 shares) {
        // {SHARE} = {UNDERLYING} * {SHARE} / {UNDERLYING} = {SHARE} ✓
        shares = assets.mulDiv(totalSupply(), totalAssets());
    }

    /// @notice Withdraw assets by burning shares
    /// @param shares D18{SHARE} Shares to burn
    /// @return assets D{X}{UNDERLYING} Assets returned
    function withdraw(uint256 shares) external returns (uint256 assets) {
        // {UNDERLYING} = {SHARE} * {UNDERLYING} / {SHARE} = {UNDERLYING} ✓
        assets = shares.mulDiv(totalAssets(), totalSupply());
    }

    /// @notice Get current exchange rate
    /// @return rate D18{UNDERLYING/SHARE} Assets per share
    function exchangeRate() external view returns (uint256 rate) {
        // {UNDERLYING/SHARE} = {UNDERLYING} * 1e18 / {SHARE}
        rate = totalAssets().mulDiv(1e18, totalSupply());
    }
}
```

### AMM / DEX

```solidity
/**
 * ═══════════════════════════════════════════════════════════
 * DIMENSIONAL GLOSSARY
 * ═══════════════════════════════════════════════════════════
 *
 * Base Dimensions:
 * - {TOKEN_A}  First token in pair
 * - {TOKEN_B}  Second token in pair
 * - {LP}       Liquidity provider token
 * - {1}        Dimensionless
 *
 * Derived Dimensions:
 * - {TOKEN_A * TOKEN_B}  Constant product invariant
 * - {TOKEN_B / TOKEN_A}  Price of A in terms of B
 */

contract AMM {
    uint256 public reserveA;     // D{X}{TOKEN_A}
    uint256 public reserveB;     // D{Y}{TOKEN_B}
    uint256 public totalSupply;  // D18{LP}
    uint256 public kLast;        // {TOKEN_A * TOKEN_B} Last invariant value
    uint256 public swapFee;      // D18{1} Fee rate (e.g., 3e15 = 0.3%)

    /// @notice Swap token A for token B
    /// @param amountAIn D{X}{TOKEN_A} Amount of token A to swap
    /// @return amountBOut D{Y}{TOKEN_B} Amount of token B received
    function swapAForB(uint256 amountAIn) external returns (uint256 amountBOut) {
        // Calculate output using constant product formula
        // (reserveA + amountAIn) * (reserveB - amountBOut) = k
        //
        // amountBOut = reserveB - k / (reserveA + amountAIn)
        // {TOKEN_B} = {TOKEN_B} - {TOKEN_A * TOKEN_B} / {TOKEN_A}
        // {TOKEN_B} = {TOKEN_B} - {TOKEN_B} = {TOKEN_B} ✓
    }

    /// @notice Get current price of A in terms of B
    /// @return price D18{TOKEN_B / TOKEN_A} Price
    function getPrice() external view returns (uint256 price) {
        // {TOKEN_B / TOKEN_A} = {TOKEN_B} * 1e18 / {TOKEN_A}
        price = reserveB.mulDiv(1e18, reserveA);
    }

    /// @notice Add liquidity
    /// @param amountA D{X}{TOKEN_A} Amount of token A
    /// @param amountB D{Y}{TOKEN_B} Amount of token B
    /// @return lpTokens D18{LP} LP tokens minted
    function addLiquidity(uint256 amountA, uint256 amountB)
        external returns (uint256 lpTokens)
    {
        // LP tokens proportional to liquidity added
        // {LP} = {LP} * {TOKEN_A} / {TOKEN_A} = {LP} ✓
        lpTokens = totalSupply.mulDiv(amountA, reserveA);
    }
}
```

### Lending Protocol

```solidity
/**
 * ═══════════════════════════════════════════════════════════
 * DIMENSIONAL GLOSSARY
 * ═══════════════════════════════════════════════════════════
 *
 * Base Dimensions:
 * - {COLLATERAL}  Collateral token (e.g., WETH)
 * - {DEBT}        Borrowed token (e.g., USDC)
 * - {USD}         Oracle price denomination
 * - {aToken}      Receipt token for deposits
 * - {s}           Time in seconds
 * - {1}           Dimensionless
 *
 * Derived Dimensions:
 * - {USD/COLLATERAL}  Collateral price
 * - {USD/DEBT}        Debt token price
 * - {1/s}             Interest rate per second
 */

contract LendingPool {
    uint256 public totalBorrowed;      // D{X}{DEBT}
    uint256 public totalCollateral;    // D{Y}{COLLATERAL}
    uint256 public liquidationRatio;   // D18{1} (e.g., 1.5e18 = 150%)
    uint256 public borrowRate;         // D27{1/s} Interest rate per second
    uint256 public lastAccrualTime;    // {s} Last interest accrual timestamp

    struct Position {
        uint256 collateral;    // D{Y}{COLLATERAL} Collateral deposited
        uint256 debt;          // D{X}{DEBT} Amount borrowed
        uint256 lastUpdate;    // {s} Timestamp of last update
    }
    mapping(address => Position) public positions;

    /// @notice Calculate health factor for a position
    /// @param collateral D{Y}{COLLATERAL} Collateral amount
    /// @param collateralPrice D8{USD/COLLATERAL} Oracle price
    /// @param debt D{X}{DEBT} Debt amount
    /// @param debtPrice D8{USD/DEBT} Oracle price
    /// @return healthFactor D18{1} Health factor (>1e18 is healthy)
    function getHealthFactor(
        uint256 collateral,
        uint256 collateralPrice,
        uint256 debt,
        uint256 debtPrice
    ) external pure returns (uint256 healthFactor) {
        // collateralValue = collateral * collateralPrice / 1e8
        // D18{USD} = D{Y}{COLLATERAL} * D8{USD/COLLATERAL} / 1e8
        uint256 collateralValue = collateral.mulDiv(collateralPrice, 1e8);

        // debtValue = debt * debtPrice / 1e8
        // D18{USD} = D{X}{DEBT} * D8{USD/DEBT} / 1e8
        uint256 debtValue = debt.mulDiv(debtPrice, 1e8);

        // healthFactor = collateralValue * 1e18 / debtValue
        // D18{1} = D18{USD} * 1e18 / D18{USD}
        healthFactor = collateralValue.mulDiv(1e18, debtValue);
    }

    /// @notice Borrow tokens against collateral
    /// @param amount D{X}{DEBT} Amount to borrow
    function borrow(uint256 amount) external {
        Position storage pos = positions[msg.sender];
        pos.debt += amount;  // {DEBT} + {DEBT} = {DEBT} ✓
        totalBorrowed += amount;  // {DEBT} + {DEBT} = {DEBT} ✓
    }

    /// @notice Deposit collateral
    /// @param amount D{Y}{COLLATERAL} Amount to deposit
    function depositCollateral(uint256 amount) external {
        Position storage pos = positions[msg.sender];
        pos.collateral += amount;  // {COLLATERAL} + {COLLATERAL} = {COLLATERAL} ✓
        totalCollateral += amount;  // {COLLATERAL} + {COLLATERAL} = {COLLATERAL} ✓
    }
}
```

---

## Step 2 Checklist

- [ ] Annotate all numeric state variables with `// D{scale}{dimension}`
- [ ] Annotate all function parameters with NatSpec dimensions
- [ ] Annotate all return values with dimensions
- [ ] Annotate all struct fields with dimensions
- [ ] Add dimensional algebra comments for non-trivial formulas
- [ ] Ensure price dimensions clearly indicate numerator/denominator
- [ ] Ensure different token types have distinct dimensions
