# TON Entry Point Detection (FunC/Tact)

## Entry Point Identification (State-Changing Only)

Focus on message handlers that modify state. **Exclude** read-only patterns:
- `get` methods in FunC (pure getters)
- Receivers that only return data without state changes

### FunC Entry Points
```func
;; Main entry point - receives all external messages
() recv_internal(int my_balance, int msg_value, cell in_msg_full, slice in_msg_body) impure {
    ;; Dispatch based on op code
    int op = in_msg_body~load_uint(32);
    if (op == op::transfer) { handle_transfer(); }
}

;; External messages (from outside blockchain)
() recv_external(slice in_msg) impure {
    ;; Usually for wallet operations
}

;; Tick-tock for special contracts
() run_ticktock(cell full_state, int is_tock) impure {
}
```

### Tact Entry Points
```tact
contract MyContract {
    // Receivers are entry points
    receive(msg: Transfer) {
        // Handle Transfer message
    }

    receive("increment") {
        // Handle text message
    }

    // External receiver
    external(msg: Deploy) {
        // Handle external message
    }

    // Bounce handler
    bounced(src: bounced<Transfer>) {
        // Handle bounced message
    }
}
```

### Entry Point Types
| Pattern | Include? | Notes |
|---------|----------|-------|
| `recv_internal` | **Yes** | All internal messages (state-changing) |
| `recv_external` | **Yes** | External (off-chain) messages |
| `receive(MsgType)` | **Yes** | Tact message handler |
| `external(MsgType)` | **Yes** | Tact external handler |
| `bounced(...)` | **Yes** | Bounce handler |
| `get` methods (FunC) | No | EXCLUDE - read-only getters |
| `get fun` (Tact) | No | EXCLUDE - read-only getters |
| Helper functions | No | Internal only |

## Access Control Patterns

### FunC Access Control
```func
;; Owner check
() check_owner() impure inline {
    throw_unless(401, equal_slices(sender_address, owner_address));
}

;; Admin check via stored address
() require_admin() impure inline {
    var ds = get_data().begin_parse();
    slice admin = ds~load_msg_addr();
    throw_unless(403, equal_slices(sender_address, admin));
}
```

### Tact Access Control
```tact
contract Owned {
    owner: Address;

    receive(msg: AdminAction) {
        require(sender() == self.owner, "Not owner");
        // ...
    }

    // Using traits
    receive(msg: Transfer) {
        self.requireOwner();  // From Ownable trait
        // ...
    }
}
```

### Op Code Dispatch Pattern (FunC)
```func
() recv_internal(...) impure {
    int op = in_msg_body~load_uint(32);

    ;; Public operations
    if (op == op::transfer) { return handle_transfer(); }
    if (op == op::swap) { return handle_swap(); }

    ;; Admin operations
    if (op == op::set_fee) {
        check_owner();
        return handle_set_fee();
    }
}
```

### Access Control Classification
| Pattern | Classification |
|---------|----------------|
| `equal_slices(sender, owner)` | Owner |
| `equal_slices(sender, admin)` | Admin |
| `require(sender() == self.owner)` | Owner |
| `self.requireOwner()` | Owner |
| `throw_unless(X, equal_slices(...))` | Check error code context |
| No sender check for op code | Public (Unrestricted) |

## Contract-Only Detection

### Callback Patterns
```func
;; Jetton transfer notification
() on_jetton_transfer(...) impure {
    ;; Should verify sender is jetton wallet
}

;; NFT callbacks
() on_nft_transfer(...) impure {
}
```

### Contract Verification
```func
;; Verify caller is expected contract
() verify_caller(slice expected) impure inline {
    throw_unless(402, equal_slices(sender_address, expected));
}
```

## Extraction Strategy

### FunC
1. Parse `.fc` / `.func` files
2. Find `recv_internal` and `recv_external` functions
3. Extract op code dispatch table:
   - Map op codes to handler functions
   - Check each handler for owner/admin checks
4. Classify:
   - Op codes with no access check → Public
   - Op codes with `check_owner`/similar → Role-based
   - Callbacks → Contract-Only

### Tact
1. Parse `.tact` files
2. Find `contract` declarations
3. Extract all `receive`, `external`, `bounced` handlers
   - **Skip** `get fun` declarations (read-only getters)
4. Check handler body for:
   - `require(sender() == self.X)` → Role-based
   - `self.requireOwner()` → Owner
   - No sender validation → Public (Unrestricted)

## TON-Specific Considerations

1. **Message-Based**: All interactions are via messages with op codes
2. **Workchains**: Check if contract operates on specific workchain
3. **Bounced Messages**: Handle bounced messages appropriately
4. **Gas Management**: `accept_message()` in FunC accepts gas payment
5. **State Init**: Initial deployment may set owner/admin

## Common Gotchas

1. **Op Code Collisions**: Different contracts may use same op codes
2. **Proxy Patterns**: Some contracts forward messages
3. **Wallet Contracts**: Special access control for wallet operations
4. **Masterchain**: Some operations require masterchain deployment
5. **Query ID**: Track request/response with query_id
