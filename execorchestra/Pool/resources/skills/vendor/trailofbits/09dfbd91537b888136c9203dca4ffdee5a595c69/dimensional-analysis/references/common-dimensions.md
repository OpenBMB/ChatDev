# Common Dimensions in DeFi

This document catalogs standard dimensional units used across DeFi protocols. While examples use Solidity syntax, the dimensional vocabulary is protocol-agnostic and applies equally to Rust (Anchor, CosmWasm), TypeScript, Python, or any other language implementing DeFi logic.

## Universal Base Units

### Token Amounts: `{tok}`

Represents a quantity of tokens.

```solidity
uint256 public totalSupply;      // {tok}
uint256 public balanceOf;        // {tok}
uint256 amount;                  // {tok}
```

**Typical precision:** D6 (USDC, USDT), D8 (WBTC), D18 (most ERC20)

### Share Amounts: `{share}`

Represents vault/pool shares.

```solidity
uint256 public totalShares;      // {share}
uint256 userShares;              // {share}
```

**Typical precision:** D18

### Time: `{s}`

Timestamps and durations in seconds.

```solidity
uint256 public lastUpdate;       // {s}
uint256 elapsed;                 // {s}
uint256 duration;                // {s}
block.timestamp                  // {s}
```

**Precision:** Integer (no decimals)

### Dimensionless: `{1}`

Pure ratios, percentages, multipliers.

```solidity
uint256 public feeRate;          // D18{1}
uint256 percent;                 // D18{1} or D4{1} for basis points
uint256 multiplier;              // D18{1}
```

**Typical precision:** D18 or D4 (basis points)

### Unit of Account: `{UoA}`

Abstract value unit, typically USD-equivalent.

```solidity
uint256 public totalValue;       // {UoA}
uint256 price;                   // {UoA} (absolute)
```

**Note:** Often implicit in price dimensions like `{UoA/tok}`

## Standard Derived Units

### Exchange Rate: `{tok/share}` or `{share/tok}`

Conversion ratio between tokens and shares.

```solidity
uint256 public exchangeRate;     // D18{tok/share}
uint256 sharePrice;              // D18{tok/share}
```

### Price: `{UoA/tok}`

Value per token in unit of account.

```solidity
uint256 public tokenPrice;       // D8{UoA/tok} (Chainlink)
uint256 oraclePrice;             // D18{UoA/tok} or D27{UoA/tok}
```

### Cross Price: `{tokA/tokB}`

Exchange rate between two tokens.

```solidity
uint256 public swapRate;         // D18{tokA/tokB}
```

### Rate Per Second: `{1/s}`

Time-based rate (fees, interest).

```solidity
uint256 public interestRate;     // D18{1/s}
uint256 feePerSecond;            // D27{1/s}
```

### Value Per Share: `{UoA/share}`

Share value in unit of account.

```solidity
uint256 public nav;              // D18{UoA/share}
uint256 shareValue;              // D27{UoA/share}
```

## Protocol-Specific Units

### Reserve Protocol

| Unit | Description | Example |
|------|-------------|---------|
| `{BU}` | Basket Unit | Target basket composition |
| `{tok/BU}` | Tokens per basket | Weight in basket |
| `{UoA/BU}` | Basket value | Basket price |
| `{BU/share}` | Baskets per share | RToken backing |
| `{RToken}` | RToken amount | Alias for `{share}` |
| `{RSR}` | RSR token amount | Staking token |

```solidity
uint256 public basketsNeeded;    // {BU}
uint256 weight;                  // D27{tok/BU}
uint256 price;                   // D27{UoA/tok}
```

### Lending Protocols (Aave, Compound)

| Unit | Description | Example |
|------|-------------|---------|
| `{debt}` | Debt token amount | Borrowed amount |
| `{collateral}` | Collateral amount | Deposited collateral |
| `{aToken}` | Aave interest-bearing token | Deposit receipt |
| `{cToken}` | Compound interest-bearing token | Deposit receipt |
| `{1}` | Health factor, LTV | Risk metrics |

```solidity
uint256 public totalDebt;        // {debt}
uint256 healthFactor;            // D18{1}
uint256 ltv;                     // D4{1} (basis points)
```

### AMM Protocols (Uniswap, Curve)

| Unit | Description | Example |
|------|-------------|---------|
| `{liq}` | Liquidity units | Pool liquidity |
| `{LP}` | LP token amount | Liquidity provider shares |
| `{sqrtP}` | Square root price | Uniswap V3 |

```solidity
uint256 public liquidity;        // {liq}
uint256 lpBalance;               // {LP}
uint160 sqrtPriceX96;            // Q96{sqrtP}
```

### Staking Protocols

| Unit | Description | Example |
|------|-------------|---------|
| `{staked}` | Staked token amount | Deposited stake |
| `{reward}` | Reward token amount | Earned rewards |
| `{reward/staked}` | Reward rate | Per-token rewards |

```solidity
uint256 public totalStaked;      // {staked}
uint256 rewardPerToken;          // D18{reward/staked}
```

## Standard Precision Levels

| Prefix | Value | Common Usage |
|--------|-------|--------------|
| D4 | 1e4 | Basis points |
| D6 | 1e6 | USDC, USDT decimals |
| D8 | 1e8 | WBTC, Chainlink prices |
| D18 | 1e18 | Standard ERC20, most calculations |
| D27 | 1e27 | High-precision prices (Reserve) |
| Q96 | 2^96 | Uniswap V3 fixed-point |

## Interface Dimensions

### ERC20

```solidity
function totalSupply() external view returns (uint256);        // {tok}
function balanceOf(address) external view returns (uint256);   // {tok}
function decimals() external view returns (uint8);             // precision info
function transfer(address, uint256 amount) external;           // amount: {tok}
function approve(address, uint256 amount) external;            // amount: {tok}
function transferFrom(address, address, uint256 amount);       // amount: {tok}
function allowance(address, address) returns (uint256);        // {tok}
```

### ERC4626

```solidity
function asset() external view returns (address);              // underlying token
function totalAssets() external view returns (uint256);        // {tok}
function convertToShares(uint256 assets) returns (uint256);    // {tok} → {share}
function convertToAssets(uint256 shares) returns (uint256);    // {share} → {tok}
function maxDeposit(address) external view returns (uint256);  // {tok}
function maxMint(address) external view returns (uint256);     // {share}
function maxWithdraw(address) external view returns (uint256); // {tok}
function maxRedeem(address) external view returns (uint256);   // {share}
function previewDeposit(uint256 assets) returns (uint256);     // {tok} → {share}
function previewMint(uint256 shares) returns (uint256);        // {share} → {tok}
function previewWithdraw(uint256 assets) returns (uint256);    // {tok} → {share}
function previewRedeem(uint256 shares) returns (uint256);      // {share} → {tok}
function deposit(uint256 assets, address) returns (uint256);   // {tok} → {share}
function mint(uint256 shares, address) returns (uint256);      // {share} → {tok}
function withdraw(uint256 assets, ...) returns (uint256);      // {tok} → {share}
function redeem(uint256 shares, ...) returns (uint256);        // {share} → {tok}
```

### Chainlink

```solidity
function decimals() external view returns (uint8);             // usually 8
function latestRoundData() external view returns (
    uint80 roundId,
    int256 answer,      // D8{UoA/tok} typically
    uint256 startedAt,  // {s}
    uint256 updatedAt,  // {s}
    uint80 answeredInRound
);
```

## Naming Convention Hints

| Pattern | Likely Dimension |
|---------|-----------------|
| `*Balance`, `*Amount` | `{tok}` |
| `*Shares`, `share*` | `{share}` |
| `*Price`, `price*` | `{UoA/tok}` |
| `*Rate`, `rate*` | `{1}` or `{1/s}` |
| `*Time`, `*Timestamp` | `{s}` |
| `*Duration`, `*Period` | `{s}` |
| `*Fee`, `fee*` | `{1}` |
| `*Ratio`, `ratio*` | `{1}` |
| `*Value`, `value*` | `{UoA}` |
| `*Per*` | derived unit |
| `total*` | aggregate amount |
| `max*`, `min*` | bounds (same as base) |
