# Dimensional Algebra Rules

This document defines the rules for dimensional arithmetic. While examples use Solidity syntax, these algebraic rules are universal and apply to any language performing fixed-point or scaled arithmetic.

## Notation

- `{A}` - A semantic unit (e.g., `{tok}`, `{share}`, `{UoA}`)
- `D18` - A precision prefix indicating 18 decimal places
- `D18{A}` - A value with unit `{A}` and precision D18
- `{A/B}` - A derived unit (A per B)
- `{A*B}` - A compound unit (A times B)
- `{1}` - Dimensionless (pure ratio)

### Formal Grammar

```
annotation     := scale? "{" dimension "}"
scale          := "D" number
dimension      := base_dim | derived_dim | "1"
derived_dim    := dimension "/" dimension | dimension "*" dimension
base_dim       := identifier
```

**Examples:**
- `{tok}` - Token amount (no scale specified)
- `D18{tok}` - Token amount, 18 decimals fixed-point
- `D27{USD/tok}` - Price, 27 decimals fixed-point
- `{1}` - Dimensionless (pure number or ratio)

## Basic Composition Rules

### Multiplication

Dimensions multiply when values are multiplied:

```
{A} * {B} = {A*B}

Examples:
{tok} * {UoA/tok} = {UoA}           # tokens × price = value
{share} * {tok/share} = {tok}       # shares × exchange rate = tokens
{1} * {A} = {A}                     # dimensionless preserves dimension
```

### Division

Dimensions divide when values are divided:

```
{A} / {B} = {A/B}

Examples:
{tok} / {share} = {tok/share}       # exchange rate
{UoA} / {tok} = {UoA/tok}           # price
{A} / {A} = {1}                     # same dimensions cancel
{A} / {1} = {A}                     # dividing by dimensionless preserves
```

### Addition and Subtraction

**CRITICAL: Addition and subtraction require identical dimensions.**

```
{A} + {A} = {A}                     # Valid
{A} - {A} = {A}                     # Valid
{A} + {B} = ERROR                   # Invalid! Dimension mismatch
{A} - {B} = ERROR                   # Invalid! Dimension mismatch

Examples:
{tok} + {tok} = {tok}               # Valid: adding token amounts
{tok} + {share} = ERROR             # Invalid: can't add tokens and shares
{UoA/tok} + {UoA/tok} = {UoA/tok}   # Valid: adding prices
```

## Precision Arithmetic

### Multiplication Precision

Precisions ADD when multiplying:

```
D18 * D18 = D36
D27 * D18 = D45
D18 * D27 = D45

Example:
D18{tok} * D18{share/tok} = D36{share}  # Need to scale down by D18
```

### Division Precision

Precisions SUBTRACT when dividing:

```
D36 / D18 = D18
D27 / D18 = D9
D18 / D18 = D0 (integer)

Example:
D36{share} / D18 = D18{share}           # Scaling down
D27{UoA/tok} / D18{1} = D9{UoA/tok}     # Precision reduced
```

### Scaling Operations

Scaling is multiplication/division by a pure precision constant:

```
D18{A} * D9 = D27{A}                    # Scale up precision
D27{A} / D9 = D18{A}                    # Scale down precision
D36{A} / D18 = D18{A}                   # Common pattern after multiplication
```

## Common Patterns

### Price Calculation

```solidity
// Calculate value from amount and price
// {UoA} = {tok} * D27{UoA/tok} / D27
// D27{UoA} = D18{tok} * D27{UoA/tok} / D18
uint256 value = Math.mulDiv(amount, price, D18);
```

### Share Conversion (ERC4626)

```solidity
// Convert assets to shares
// {share} = {tok} * {share} / {tok}
// D18{share} = D18{tok} * D18{share} / D18{tok}
uint256 shares = Math.mulDiv(assets, totalSupply, totalAssets);

// Convert shares to assets
// {tok} = {share} * {tok} / {share}
uint256 assets = Math.mulDiv(shares, totalAssets, totalSupply);
```

### Fee Application

```solidity
// Apply percentage fee
// {tok} = {tok} * D18{1} / D18
uint256 fee = Math.mulDiv(amount, feeRate, D18);
uint256 netAmount = amount - fee;
```

### Rate Per Second

```solidity
// Calculate accrued amount
// {tok} = {tok} * D18{1/s} * {s} / D18
uint256 accrued = Math.mulDiv(principal, rate * elapsed, D18);
```

### Cross-Rate Calculation

```solidity
// Calculate token A price in terms of token B
// D27{B/A} = D27{UoA/A} * D27 / D27{UoA/B}
uint256 crossRate = Math.mulDiv(priceA, D27, priceB);
```

## Dimensional Simplification

### Cancellation

When the same unit appears in numerator and denominator, it cancels:

```
{tok/share} * {share} = {tok}           # share cancels
{UoA/tok} * {tok/BU} = {UoA/BU}         # tok cancels
{A/B} * {B/C} = {A/C}                   # B cancels
```

### Identity

```
{A} * {1} = {A}
{A} / {1} = {A}
{A} * {B/B} = {A}                       # Multiplying by 1
```

## Multi-Step Calculations

For complex expressions, track dimensions step by step:

```solidity
// Calculate share value in UoA
// Step 1: {tok/share} = {tok} / {share}
// Step 2: {UoA/share} = {tok/share} * {UoA/tok}
//
// In code:
// D18{UoA/share} = D18{tok} * D27{UoA/tok} / D18{share} / D9
uint256 shareValue = Math.mulDiv(
    Math.mulDiv(totalAssets, price, totalShares),
    1,
    1e9  // Scale D27 to D18
);
```

## Error Patterns

### Division Before Multiplication

**Risky for precision loss:**
```solidity
// BAD: May lose precision
uint256 result = a / b * c;

// BETTER: Use mulDiv
uint256 result = Math.mulDiv(a, c, b);
```

### Missing Scaling

**Common bug pattern:**
```solidity
// BUG: D36 result stored in D18 variable
uint256 result = amount * rate;  // D18 * D18 = D36!

// CORRECT:
uint256 result = Math.mulDiv(amount, rate, D18);
```

### Wrong Scaling Direction

```solidity
// BUG: Multiplied when should divide
uint256 price18 = price27 * 1e9;  // Now D36!

// CORRECT:
uint256 price18 = price27 / 1e9;
```

## Special Cases

### Dimensionless Constants

Integer constants like `2`, `100`, `MAX_UINT` are dimensionless `{1}`:

```solidity
uint256 doubled = amount * 2;     // {tok} * {1} = {tok}
uint256 half = amount / 2;        // {tok} / {1} = {tok}
```

### Timestamps

Timestamps and durations have dimension `{s}` (seconds):

```solidity
uint256 elapsed = block.timestamp - lastUpdate;  // {s} - {s} = {s}
uint256 rate = feePerSecond * elapsed;           // {1/s} * {s} = {1}
```

### Basis Points

Basis points are `{1}` with implicit D4 precision:

```solidity
uint256 constant BPS = 10000;     // D4
uint256 fee = amount * feeBps / BPS;  // {tok} * {1} / {1} = {tok}
```

## Validation Checklist

For any arithmetic operation:

1. ✓ Do operand dimensions combine correctly?
2. ✓ Is the result dimension what's expected?
3. ✓ Is precision handled correctly (scaling)?
4. ✓ Is rounding direction appropriate?
5. ✓ Could intermediate values overflow?
