# Vyper Entry Point Detection

## Entry Point Identification (State-Changing Only)

### Include: State-Changing Functions
```vyper
@external                    # State-changing entry point
def function_name():
    pass

@external
@payable                     # State-changing, receives ETH
def payable_function():
    pass

@external
@nonreentrant("lock")        # State-changing with reentrancy protection
def protected():
    pass
```

### Exclude: Read-Only Functions
```vyper
@external
@view                        # EXCLUDE - cannot modify state
def read_only():
    pass

@external
@pure                        # EXCLUDE - no state access
def pure_function():
    pass
```

### Decorator Matrix
| Decorators | Include? | Notes |
|------------|----------|-------|
| `@external` | **Yes** | State-changing entry point |
| `@external @payable` | **Yes** | State-changing, receives ETH |
| `@external @nonreentrant` | **Yes** | State-changing with protection |
| `@external @view` | No | Read-only, exclude |
| `@external @pure` | No | No state access, exclude |
| `@internal` | No | Not externally callable |
| `@deploy` | No | Constructor (Vyper 0.4+) |

### Special Entry Points
```vyper
@external
@payable
def __default__():           # Fallback function (receives ETH + unmatched calls)
    pass
```

## Access Control Patterns

### Owner Pattern
```vyper
owner: public(address)

@external
def restricted_function():
    assert msg.sender == self.owner, "Not owner"
    # ...
```

### Role-Based Patterns
```vyper
# Common patterns
admin: public(address)
governance: public(address)
guardian: public(address)
operator: public(address)

# Mapping-based roles
authorized: public(HashMap[address, bool])
minters: public(HashMap[address, bool])

@external
def mint(to: address, amount: uint256):
    assert self.minters[msg.sender], "Not minter"
    # ...
```

### Access Control Classification
| Pattern | Classification |
|---------|----------------|
| `assert msg.sender == self.owner` | Admin/Owner |
| `assert msg.sender == self.admin` | Admin |
| `assert msg.sender == self.governance` | Governance |
| `assert msg.sender == self.guardian` | Guardian |
| `assert self.authorized[msg.sender]` | Review Required |
| `assert self.whitelist[msg.sender]` | Review Required |

## Contract-Only Detection

### Callback Functions
```vyper
@external
def onERC721Received(...) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)")

@external
def uniswapV3SwapCallback(amount0: int256, amount1: int256, data: Bytes[...]):
    # Must verify caller is the pool
    pass
```

### Contract-Caller Checks
```vyper
assert msg.sender == self.pool, "Only pool"
assert msg.sender != tx.origin, "No EOA"  # Vyper 0.3.7+
```

## Extraction Strategy

1. Parse all `.vy` files
2. For each function:
   - Check for `@external` decorator
   - **Skip** functions with `@view` or `@pure` decorators
   - Record function name and parameters
   - Record line number
   - Check for access control assertions in function body
3. Classify:
   - No access assertions → Public (Unrestricted)
   - `msg.sender == self.X` → Check what X is
   - `self.mapping[msg.sender]` → Review Required
   - Known callback name → Contract-Only

## Vyper-Specific Considerations

1. **No Modifiers**: Vyper doesn't have modifiers—access control is inline `assert` statements
2. **No Inheritance**: Each contract is standalone (interfaces only)
3. **Explicit is Better**: All visibility must be declared explicitly
4. **Default Internal**: Functions without decorators are internal

## Common Gotchas

1. **Initializer Pattern**: Look for `initialized: bool` flag with one-time setup
2. **Raw Calls**: `raw_call()` can delegate to other contracts
3. **Create Functions**: `create_minimal_proxy_to()`, `create_copy_of()` are factory patterns
4. **Reentrancy**: `@nonreentrant` protects against reentrancy but function is still entry point
