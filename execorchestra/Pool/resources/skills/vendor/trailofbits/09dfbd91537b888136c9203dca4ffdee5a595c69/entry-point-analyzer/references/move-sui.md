# Move Entry Point Detection (Sui)

## Entry Point Identification (State-Changing Only)

In Move, `public` functions can be invoked from programmable transaction blocks (Sui) or transaction scripts (Aptos) and typically modify state. In addition, private `entry` functions are entrypoints. Package-protected (`public(package) fun`) and private (`fun`) functions should be excluded.

```move
// Public functions
public fun compute(obj: &mut Object): u64 { }

// Entry functions in Sui
public entry fun transfer(ctx: &mut TxContext) { }
```

### Visibility Rules
| Visibility | Include? | Notes |
|------------|----------|-------|
| `public entry fun` | **Yes** | Callable from transactions and modules |
| `public fun` | **Yes** | Callable from transactions and modules |
| `entry fun` | **Yes** | Callable from transactions, but not other modules |
| `fun` (private) | No | Not externally callable |
| `public(package) fun` | No | Only callable by other modules in the same package |

## Access Control Patterns

```move
// Object types have the key ability
public struct MyObject has key { id: ID, ... }

// Capability objects typically have names that end with "Cap"
public struct AdminCap has key { id: ID, ... }

// Shared objects are created via `public_share
public struct Pool has key { id: ID, ... }

// Object ownership provides access control
public fun use_owned_object(obj: &mut MyObject) {
    // Only owner of obj can call this
}

// Shared object - anyone can access
public fun use_shared(pool: &mut Pool) { }

// Shared Pool object gated by capability - only owner of AdminCap can call
public fun capability_gate(_cap: &AdminCap, pool: &mut Pool) {}
```

### Access Control Classification
| Pattern | Classification |
|---------|----------------|
| Owned object parameter | Owner of object |
| Shared object | Public (Unrestricted) |

## Contract-Only Detection

### Package-protected Functions
```move
// Only callable by other modules in the same Move package
public(protected) fun internal_fun() { }
```

## Extraction Strategy

1. Parse all `.move` files
2. Find `module` declarations
3. Extract `public`, `public entry`, and `entry` functions
4. Extract object type declarations (`struct`'s that have the `key` ability)
5. Determine whether each object type is **owned** (passed as parameter to `transfer` or `public_transfer` functions) or **shared** (passed as parameter to `share` or `public_share` functions)
6. Analyze parameters:
   - Owned object type with "XCap" in name -> X role (e.g., AdminCap = Admin role, GuardianCap = Guardian role)
   - Owned object type without "Cap" in name -> Owner role
   - Shared object type -> Public

## Move-Specific Considerations

1. **Object Model**: Access control typically through object ownership (rather than runtime assertions)
2. **Capabilities**: `Cap` suffix typically indicates capability pattern
4. **Generic Types**: Type parameters may carry capability constraints
5. **Package Visibility**: `public(pacakge)` limits callers to modules in the same package

## Common Gotchas

1. **Module Initializers**: `init` functions often create singletone shared objects and initial capabilities
2. **Object Wrapping**: Wrapped objects transfer ownership
3. **Shared vs Owned**: Shared objects can be accessed by anyone, owned objects only by a transaction sent by the owner
4. **Package Upgrades**: Upgrades can introduce new types and functions and change old ones in type-compatible ways
5. **Phantom Types**: Type parameters with `phantom` don't affect runtime
