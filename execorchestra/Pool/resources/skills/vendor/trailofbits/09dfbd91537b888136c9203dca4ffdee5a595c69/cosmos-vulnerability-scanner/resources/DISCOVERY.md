## Discovery & CLAUDE.md Generation

Explore the codebase and write a `CLAUDE.md` at the target repo root with all context needed for the audit.

### Platform Detection

Determine what you're auditing:
- **Pure Cosmos SDK**: `go.mod` imports `cosmossdk.io/*` or `github.com/cosmos/cosmos-sdk/*`
- **EVM-based (Ethermint/Evmos)**: `go.mod` imports `github.com/evmos/ethermint` or `github.com/evmos/evmos`; has `x/evm` module
- **CosmWasm**: `go.mod` imports `github.com/CosmWasm/wasmd`; or `.rs` contracts with `use cosmwasm_std::*`
- **IBC enabled**: `go.mod` imports `github.com/cosmos/ibc-go`; has IBC keepers or `x/ibc*` modules

### Technical Inventory

Identify and record:
1. SDK version and ibc-go version from `go.mod`
2. Custom modules under `x/*/` — list each with one-line purpose
3. ABCI hooks per module (`HasBeginBlocker`, `HasEndBlocker`, `HasPreBlocker`, `HasPrecommit`, `HasPrepareCheckState`, `HasABCIEndBlock`)
4. Message types from `proto/.../tx.proto` — list each with its `cosmos.msg.v1.signer` field
5. Handlers in `keeper/msg_server.go` — note any stub/no-op implementations
6. Keepers that hold references to `bankKeeper`, `stakingKeeper`, `authzKeeper`
7. AnteHandler chain from `app.go` or `ante.go` — list decorators in order
8. IBC integration: IBC modules, middleware stack, ICA host/controller, PFM

### Threat Model

Determine and record:
1. **What the chain does**: DEX, lending, bridge, staking derivatives, NFT, general-purpose, etc.
2. **High-value assets**: tokens held in escrow, module accounts with mint/burn authority, LP pools, vaults
3. **Trust boundaries**: which actors are trusted (validators, governance, relayers, oracles, IBC counterparties) and what each can do
4. **External integrations**: IBC channels (which chains, which tokens), oracles, bridges, off-chain components
5. **Custom crypto or consensus**: vote extensions, custom ABCI++, custom mempool (`PrepareProposal`/`ProcessProposal`), MEV protection
6. **Upgrade history**: recent migrations, deprecated modules still present, parameter changes

### CLAUDE.md Structure

Write the CLAUDE.md as a structured reference for the auditor:

```markdown
# Chain Audit Context

## Versions
- Cosmos SDK: v0.50.x
- ibc-go: v8.x

## Modules
| Module | Purpose | ABCI Hooks | Bank Access |
|--------|---------|------------|-------------|
| x/dex  | Order book DEX | EndBlocker (match orders) | Yes (escrow) |

## Message Types
| Message | Signer Field | Handler |
|---------|-------------|---------|
| MsgPlaceOrder | sender | msg_server.go:42 |

## Threat Model
- **Chain purpose**: DEX with IBC token support
- **High-value targets**: escrow account (holds all deposited tokens), LP pools
- **Trust boundaries**: validators (order matching), relayers (IBC), governance (params)
- **IBC exposure**: channels to Osmosis, Cosmos Hub; PFM enabled

## AnteHandler Chain
1. SetUpContext → 2. ... → N. SigVerification

## Audit Focus Areas
[Based on threat model, which vulnerability categories matter most]
```
