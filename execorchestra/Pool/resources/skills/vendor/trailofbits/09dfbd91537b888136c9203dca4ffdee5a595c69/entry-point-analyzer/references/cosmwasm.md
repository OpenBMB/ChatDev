# CosmWasm Entry Point Detection

## Entry Point Identification (State-Changing Only)

### Include: State-Changing Entry Points
```rust
// Instantiate - called once on deployment
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn instantiate(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> { }

// Execute - main entry point for state changes
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> { }

// Query - read-only entry point
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn query(
    deps: Deps,
    env: Env,
    msg: QueryMsg,
) -> StdResult<Binary> { }

// Migrate - called on contract migration
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn migrate(
    deps: DepsMut,
    env: Env,
    msg: MigrateMsg,
) -> Result<Response, ContractError> { }

// Reply - handles submessage responses
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn reply(
    deps: DepsMut,
    env: Env,
    msg: Reply,
) -> Result<Response, ContractError> { }

// Sudo - privileged operations (governance)
#[cfg_attr(not(feature = "library"), entry_point)]
pub fn sudo(
    deps: DepsMut,
    env: Env,
    msg: SudoMsg,
) -> Result<Response, ContractError> { }
```

### Entry Point Types
| Entry Point | Include? | Classification | Notes |
|-------------|----------|----------------|-------|
| `instantiate` | **Yes** | One-time setup | Sets initial state |
| `execute` | **Yes** | Main dispatcher | Contains multiple operations |
| `query` | No | Read-only | EXCLUDE - no state changes |
| `migrate` | **Yes** | Admin/Governance | Requires migration permission |
| `reply` | **Yes** | Contract-Only | Submessage callback |
| `sudo` | **Yes** | Governance | Chain-level privileged |

### ExecuteMsg Variants (Primary Focus)
```rust
#[cw_serde]
pub enum ExecuteMsg {
    Transfer { recipient: String, amount: Uint128 },     // Usually public
    UpdateConfig { admin: Option<String> },              // Admin only
    Pause {},                                            // Guardian
    Withdraw { amount: Uint128 },                        // Public or restricted
}
```

## Access Control Patterns

### Cw-Ownable Pattern
```rust
use cw_ownable::{assert_owner, initialize_owner};

pub fn execute_admin_action(deps: DepsMut, info: MessageInfo) -> Result<...> {
    assert_owner(deps.storage, &info.sender)?;
    // ...
}
```

### Manual Owner Check
```rust
pub fn execute_update_config(deps: DepsMut, info: MessageInfo) -> Result<...> {
    let config = CONFIG.load(deps.storage)?;
    if info.sender != config.owner {
        return Err(ContractError::Unauthorized {});
    }
    // ...
}
```

### Role-Based Access
```rust
// Common patterns
if info.sender != state.admin { return Err(Unauthorized); }
if info.sender != state.governance { return Err(Unauthorized); }
if !state.operators.contains(&info.sender) { return Err(Unauthorized); }

// Using cw-controllers
use cw_controllers::Admin;
ADMIN.assert_admin(deps.as_ref(), &info.sender)?;
```

### Access Control Classification
| Pattern | Classification |
|---------|----------------|
| `assert_owner(storage, &sender)` | Owner |
| `ADMIN.assert_admin(deps, &sender)` | Admin |
| `info.sender != config.owner` | Owner |
| `info.sender != config.admin` | Admin |
| `info.sender != config.governance` | Governance |
| `!operators.contains(&sender)` | Operator |
| `!guardians.contains(&sender)` | Guardian |
| No sender check | Public (Unrestricted) |

## Contract-Only Detection

### Reply Handler
```rust
#[entry_point]
pub fn reply(deps: DepsMut, env: Env, msg: Reply) -> Result<Response, ContractError> {
    match msg.id {
        INSTANTIATE_REPLY_ID => handle_instantiate_reply(deps, msg),
        _ => Err(ContractError::UnknownReplyId { id: msg.id }),
    }
}
```

### Callback Messages
```rust
// Messages expected from other contracts
ExecuteMsg::Callback { ... } => {
    // Should verify sender is expected contract
    if info.sender != expected_contract {
        return Err(ContractError::Unauthorized {});
    }
}
```

## Extraction Strategy

1. **Find Message Enums**:
   - `ExecuteMsg` - main operations (INCLUDE)
   - `QueryMsg` - read operations (EXCLUDE)
   - `SudoMsg` - governance operations (INCLUDE)

2. **For Each ExecuteMsg Variant**:
   - Find handler function (usually `execute_<variant_name>`)
   - Check for access control at start of function
   - Classify by access pattern

3. **Map Entry Points**:
   - `execute` dispatcher → enumerate variants (state-changing)
   - `query` → **SKIP** (read-only, no state changes)
   - `sudo` → all variants are governance-level
   - `reply` → contract-only callbacks

## CosmWasm-Specific Considerations

1. **Message Info**: `info.sender` is the caller address
2. **Query Has No Sender**: Queries are stateless, no access control
3. **Sudo Is Privileged**: Only callable by chain governance
4. **Submessages**: `reply` handles responses from submessages
5. **IBC**: IBC entry points for cross-chain messages

## Common Gotchas

1. **Instantiate Race**: First caller sets owner if not careful
2. **Migration Admin**: Separate from contract admin
3. **Cw20 Callbacks**: `Cw20ReceiveMsg` is a callback pattern
4. **IBC Callbacks**: `ibc_packet_receive` etc. are entry points
5. **Admin vs Owner**: May be different addresses
