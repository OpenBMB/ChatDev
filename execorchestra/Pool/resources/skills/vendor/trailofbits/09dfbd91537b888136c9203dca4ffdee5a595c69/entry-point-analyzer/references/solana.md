# Solana Entry Point Detection

## Entry Point Identification (State-Changing Only)

In Solana, most program instructions modify state. **Exclude** view-only patterns:
- Instructions that only read account data without `mut` references
- Pure computation functions that don't write to accounts

### Native Solana Programs
```rust
// Single entrypoint macro
entrypoint!(process_instruction);

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    // Dispatch to handlers based on instruction_data
}
```

### Anchor Framework
```rust
#[program]
mod my_program {
    use super::*;

    // Each pub fn is an entry point
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> { }
    pub fn transfer(ctx: Context<Transfer>, amount: u64) -> Result<()> { }
}
```

### Entry Point Detection Rules
| Pattern | Include? | Notes |
|---------|----------|-------|
| `entrypoint!(fn_name)` | **Yes** | Native program entry |
| `pub fn` inside `#[program]` mod with `mut` accounts | **Yes** | Anchor state-changing |
| `pub fn` inside `#[program]` mod (view-only) | No | Exclude if no `mut` accounts |
| Functions in `processor.rs` matching instruction enum | **Yes** | Native pattern |
| Internal helper functions | No | Not externally callable |

## Access Control Patterns

### Anchor Constraints
```rust
#[derive(Accounts)]
pub struct AdminOnly<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,

    #[account(
        constraint = config.admin == admin.key() @ ErrorCode::Unauthorized
    )]
    pub config: Account<'info, Config>,
}
```

### Common Access Control Patterns
| Pattern | Classification |
|---------|----------------|
| `constraint = X.admin == signer.key()` | Admin |
| `constraint = X.owner == signer.key()` | Owner |
| `constraint = X.authority == signer.key()` | Authority (Admin-level) |
| `constraint = X.governance == signer.key()` | Governance |
| `constraint = X.guardian == signer.key()` | Guardian |
| `has_one = admin` | Admin |
| `has_one = owner` | Owner |
| `has_one = authority` | Authority |
| `Signer` account with no constraints | Review Required |

### Native Access Control
```rust
// Check signer
if !accounts[0].is_signer {
    return Err(ProgramError::MissingRequiredSignature);
}

// Check specific authority
if accounts[0].key != &expected_authority {
    return Err(ProgramError::InvalidAccountData);
}
```

### Access Control Macros (Anchor)
```rust
#[access_control(is_admin(&ctx))]
pub fn admin_function(ctx: Context<AdminAction>) -> Result<()> { }

fn is_admin(ctx: &Context<AdminAction>) -> Result<()> {
    require!(ctx.accounts.admin.key() == ADMIN_PUBKEY, Unauthorized);
    Ok(())
}
```

## Contract-Only Detection (CPI Patterns)

### Cross-Program Invocation Sources
```rust
// Functions expected to be called via CPI
pub fn on_token_transfer(ctx: Context<TokenCallback>, amount: u64) -> Result<()> {
    // Should verify calling program
    require!(
        ctx.accounts.calling_program.key() == expected_program::ID,
        ErrorCode::InvalidCaller
    );
}
```

### CPI Verification Patterns
```rust
// Verify CPI caller
let calling_program = ctx.accounts.calling_program.key();
require!(calling_program == &spl_token::ID, InvalidCaller);

// Check instruction sysvar for CPI
let ix = load_current_index_checked(&ctx.accounts.instruction_sysvar)?;
```

## Extraction Strategy

1. **Detect Framework**:
   - Check `Cargo.toml` for `anchor-lang` → Anchor
   - Check for `entrypoint!` macro → Native

2. **For Anchor**:
   - Find `#[program]` module
   - Extract all `pub fn` within it
   - Parse `#[derive(Accounts)]` structs for constraints

3. **For Native**:
   - Find instruction enum (usually in `instruction.rs`)
   - Map variants to handler functions in `processor.rs`
   - Check each handler for signer/authority checks

4. **Classify**:
   - No authority constraints → Public (Unrestricted)
   - `has_one`, `constraint` with authority → Role-based
   - CPI-only patterns → Contract-Only

## Solana-Specific Considerations

1. **Account Validation**: Access control often via account constraints, not function-level
2. **PDA Authority**: Program Derived Addresses can act as authorities
3. **Signer vs Authority**: `Signer` alone doesn't mean admin—check what the signer controls
4. **Instruction Data**: Native programs dispatch based on instruction discriminator

## Common Gotchas

1. **Initialize Patterns**: `is_initialized` checks—first caller may set authority
2. **Upgrade Authority**: Programs can be upgraded—check upgrade authority
3. **Multisig**: Some operations require multiple signers
4. **CPI Safety**: Functions callable via CPI should verify calling program
5. **Freeze Authority**: Token accounts may have freeze authority
