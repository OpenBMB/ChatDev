# Solidity Entry Point Detection

## Entry Point Identification (State-Changing Only)

### Include: State-Changing Functions
```solidity
function name() external { }           // State-changing entry point
function name() external payable { }   // State-changing, receives ETH
function name() public { }             // State-changing entry point
```

### Exclude: Read-Only Functions
```solidity
function name() external view { }      // EXCLUDE - cannot modify state
function name() external pure { }      // EXCLUDE - no state access
function name() public view { }        // EXCLUDE - cannot modify state
```

### Visibility and Mutability Matrix
| Visibility | Mutability | Include? | Notes |
|------------|------------|----------|-------|
| `external` | (none) | **Yes** | State-changing entry point |
| `external` | `payable` | **Yes** | State-changing, receives ETH |
| `external` | `view` | No | Read-only, exclude |
| `external` | `pure` | No | No state access, exclude |
| `public` | (none) | **Yes** | State-changing entry point |
| `public` | `payable` | **Yes** | State-changing, receives ETH |
| `public` | `view` | No | Read-only, exclude |
| `public` | `pure` | No | No state access, exclude |
| `internal` | any | No | Not externally callable |
| `private` | any | No | Not externally callable |

### Special Entry Points
- `receive() external payable` — Receives plain ETH transfers
- `fallback() external` — Catches unmatched function calls
- `constructor()` — One-time initialization (not recurring entry point)

## Access Control Patterns

### OpenZeppelin Patterns
```solidity
// Ownable
modifier onlyOwner() { require(msg.sender == owner); }

// AccessControl
modifier onlyRole(bytes32 role) { require(hasRole(role, msg.sender)); }

// Common role constants
bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
```

### Common Modifier Names → Role Classification
| Modifier Pattern | Classification |
|------------------|----------------|
| `onlyOwner` | Admin/Owner |
| `onlyAdmin` | Admin |
| `onlyRole(ADMIN_ROLE)` | Admin |
| `onlyRole(GOVERNANCE_ROLE)` | Governance |
| `onlyGovernance` | Governance |
| `onlyGuardian` | Guardian |
| `onlyPauser`, `whenNotPaused` | Guardian/Pauser |
| `onlyMinter` | Minter |
| `onlyOperator` | Operator |
| `onlyKeeper` | Keeper |
| `onlyRelayer` | Relayer |
| `onlyStrategy`, `onlyStrategist` | Strategist |
| `onlyVault` | Contract-Only |

### Inline Access Control (Flag for Review)
```solidity
require(msg.sender == someAddress, "...");      // Check who someAddress is
require(authorized[msg.sender], "...");         // Dynamic authorization
require(whitelist[msg.sender], "...");          // Whitelist pattern
if (msg.sender != admin) revert();              // Inline admin check
```

## Contract-Only Detection

### Callback Functions
```solidity
// ERC token callbacks
function onERC721Received(...) external returns (bytes4)
function onERC1155Received(...) external returns (bytes4)
function onERC1155BatchReceived(...) external returns (bytes4)

// DeFi callbacks
function uniswapV3SwapCallback(...) external
function uniswapV3MintCallback(...) external
function pancakeV3SwapCallback(...) external
function algebraSwapCallback(...) external

// Flash loan callbacks
function onFlashLoan(...) external returns (bytes32)
function executeOperation(...) external returns (bool)  // Aave
function receiveFlashLoan(...) external                 // Balancer
```

### Contract-Caller Checks
```solidity
require(msg.sender == address(pool), "...");    // Specific contract
require(msg.sender != tx.origin, "...");        // Must be contract
require(tx.origin != msg.sender);               // No EOA calls
```

## Extraction Strategy

1. Parse all `.sol` files
2. For each contract/interface/abstract:
   - Extract `external` and `public` functions
   - **Skip** functions with `view` or `pure` modifiers
   - Record function signature: `name(paramTypes)`
   - Record line number
   - Extract all modifiers applied
3. Classify by modifiers:
   - No access modifiers → Public (Unrestricted)
   - Known role modifier → Appropriate role category
   - Inline `require(msg.sender...)` → Review Required
   - Callback pattern → Contract-Only

## Inheritance Considerations

- Check parent contracts for modifier definitions
- A function may inherit access control from overridden function
- Abstract contracts may define modifiers used by children
- Interfaces define signatures but not access control

## Common Gotchas

1. **Initializers**: `initialize()` often has `initializer` modifier but may be unrestricted on first call
2. **Proxies**: Implementation contracts may have different access patterns than proxies
3. **Upgrades**: `upgradeTo()`, `upgradeToAndCall()` are high-privilege
4. **Multicall**: `multicall(bytes[])` allows batching—check what it can call
5. **Permit**: `permit()` functions enable gasless approvals—check EIP-2612 compliance
