# Cosmos Vulnerability Scanner — Update Log

## Third Update (2026-03-18) — 8 Missing Bug Classes Added

### Summary
Added 8 missing vulnerability classes identified from real-world Cosmos findings catalog. Skill now covers 28 VULNERABILITY_PATTERNS + 16 IBC patterns. No existing patterns were duplicated.

### New Patterns in VULNERABILITY_PATTERNS.md
- **§20 expanded**: ROUNDING ERRORS → ARITHMETIC ERRORS. Added wrapping overflow (CWA-2024-002), wrong operand (Osmosis $5M), negative value validation (Barberry vesting poisoning)
- **§22 expanded**: Added CacheContext event leak pattern (Huckleberry — events persist after state rollback, enables bridge spoofing)
- **§24 expanded**: EVMOS/ETHERMINT-SPECIFIC → EVM/COSMOS STATE DESYNC. Full precompile atomicity section with 6 detection patterns from 7 findings ($7M+ real losses)
- **§25 new**: STORAGE KEY DESIGN FLAWS — string concatenation collisions, prefix iterator malleability, redelegation bypass
- **§26 new**: CONSENSUS VALIDATION GAPS — vote extension forgery (SEDA), block timestamp manipulation (CometBFT Tachyon), vesting on blocked addresses
- **§27 new**: CIRCUIT BREAKER AUTHZ BYPASS — x/circuit scope escalation
- **§28 new**: MERKLE PROOF / CRYPTOGRAPHIC VERIFICATION FLAWS — ICS-23 proof forgery (Dragonberry), IAVL RangeProof (Dragonfruit/$566M), ECDSA malleability (Gravity Bridge)

### New Pattern in IBC_VULNERABILITY_PATTERNS.md
- **§16 new**: IBC REENTRANCY / CEI VIOLATIONS — OnTimeoutPacket reentrancy (ASA-2024-007, $150M+ at risk), Terra IBC hooks ($6.4M stolen)

### SKILL.md Updates
- Updated description, Step 2 checklist, IBC reference count, and Priority Guidelines

---

## Second Update (2026-03-06) — v0.53.x Re-validation + 4 New Patterns

### Summary
Re-validated all 9 existing patterns against cosmos-sdk v0.53.x (commit `82fcb05ceb`, CometBFT v0.38.21, `cosmossdk.io/math` v1.5.3, `cosmossdk.io/collections` v1.3.1). Added 4 new vulnerability patterns discovered during verification. Skill now covers 13 patterns.

### Existing Pattern Corrections

**Pattern 4.4 (Slow ABCI Methods)**:
- Added `HasABCIEndBlock` (returns `[]abci.ValidatorUpdate, error`) as a second EndBlock interface alongside `HasEndBlocker` (returns `error`). Used by x/staking. The skill previously only mentioned one variant.
- Added `HasPrecommit` and `HasPrepareCheckState` as additional lifecycle hooks (confirmed in `core/appmodule/module.go:42-53`). These run after EndBlock and are potential DoS surfaces.

**Pattern 4.5 (ABCI Panics)**:
- Added note about `ValidateBasic()` deprecation (`types/tx_msg.go:102`: "deprecated and now facultative"). This increases the likelihood of invalid inputs reaching panic-prone code in ABCI methods.

### New Patterns Added

**4.10 Unbounded Pagination / Query DoS** (HIGH):
- `types/query/pagination.go` `DefaultLimit=100` only applies when `Limit==0`. Any non-zero client-supplied limit is accepted without cap.
- Recent fix `d9d77304fd` partially addressed this in `x/auth/tx` and `x/bank/keeper/genesis.go`, but core pagination still lacks a hard maximum.

**4.11 Event Override / Suppression** (MEDIUM):
- New `EventManager.OverrideEvents()` method added in commit `2ddb9ac0a9` (`types/events.go:63`). Replaces all previously emitted events.
- If called in module code, can silently suppress events from auth, bank, IBC — breaking indexers and relayers.

**4.12 Unordered Transaction Replay** (HIGH):
- SDK v0.53 supports `TxBody.Unordered=true` with timestamp-based replay protection.
- Configurable via `WithMaxUnorderedTxTimeoutDuration` (default 10min) and `WithUnorderedTxGasCost` (default 2240).
- `x/auth` PreBlocker handles `RemoveExpiredUnorderedNonces` cleanup.
- Risks: insufficient timeout, nonce flooding DoS, ordering assumptions in app logic.

**4.13 Missing msg_server Validation** (HIGH):
- `ValidateBasic()` is now deprecated and facultative (`types/tx_msg.go:102`).
- Modules migrating away from `ValidateBasic` may forget to add equivalent validation in `msg_server.go` handlers.
- Authority/signer checks must be in the handler, not just in the removed `ValidateBasic`.

### Verification Notes

All patterns confirmed against the live codebase:
- `sdk.Msg = proto.Message` (types/tx_msg.go:19) — confirmed
- 0 `GetSigners() []AccAddress` methods in x/ — confirmed (only `LegacyMsg` interface defines it)
- 74 `cosmos.msg.v1.signer` annotations across 22 proto files — confirmed
- `appmodule.HasBeginBlocker`, `HasEndBlocker`, `HasPreBlocker` in core/appmodule/module.go:65-89 — confirmed
- `module.HasABCIEndBlock` in types/module/module.go:237-241 — confirmed (different return type!)
- `appmodule.HasPrecommit`, `HasPrepareCheckState` in core/appmodule/module.go:42-53 — confirmed
- `x/auth/module.go` and `x/upgrade/module.go` implement `PreBlock` — confirmed
- `time.Now()` only in test files under x/, not consensus code — confirmed
- `go func` only in generated `pb.gw.go` files under x/ — confirmed
- `blockedAddrs` mechanism in x/bank/keeper/keeper.go — confirmed
- `QuoTruncate`/`QuoRoundUp` on `math.LegacyDec` in math/legacy_dec.go — confirmed
- No handler.go files for legacy SDK handler pattern under x/ — confirmed
- 22 modules under x/ (no x/accounts in this version) — confirmed
- `collections` framework used extensively (81+ occurrences in keeper.go files) — confirmed

---

# First Update (2026-03-06)

## Context

The skill's vulnerability patterns were written for Cosmos SDK ~v0.46 and had not been updated for the breaking changes in v0.47–v0.53. The current cosmos-sdk codebase (v0.53.x, Go 1.23, `cosmossdk.io/math` v1.5.3) was used as the reference for validation.

---

## 1. Mismatched Pattern Summary in SKILL.md

**Problem**: [SKILL.md:98–109](SKILL.md) Section 5 listed 9 CosmWasm-specific patterns (Missing Denom Validation, Reentrancy via Submessages, etc.) that did not correspond to the actual 9 Cosmos SDK patterns defined in [VULNERABILITY_PATTERNS.md](resources/VULNERABILITY_PATTERNS.md). The summary and the resource file described completely different vulnerability classes.

**Fix**: Replaced the summary to accurately reflect the 9 patterns in the resource file.

---

## 2. Pattern 4.1 — GetSigners: Rewritten for Proto Annotations

**Problem**: The pattern described `GetSigners() []sdk.AccAddress` as a method on message types. This interface was removed in SDK v0.47. In the current codebase:

- `sdk.Msg` is just `proto.Message` — [types/tx_msg.go:19](cosmos-sdk/types/tx_msg.go)
- No `func.*GetSigners.*[]sdk.AccAddress` methods exist anywhere in `x/`
- Signers are declared via `cosmos.msg.v1.signer` proto annotations — e.g. [proto/cosmos/gov/v1/tx.proto:60](cosmos-sdk/proto/cosmos/gov/v1/tx.proto)
- Resolution happens in `x/tx/signing` — [x/tx/signing/context.go:358](cosmos-sdk/x/tx/signing/context.go) (`func (c *Context) GetSigners`)

**Fix**: Rewrote pattern to describe the modern vulnerability: mismatch between `cosmos.msg.v1.signer` proto annotation and the field actually used for authorization in `msg_server.go`. Added detection patterns for wrong field annotation and proto vs handler mismatch.

---

## 3. Pattern 4.2 — Non-Determinism: Math Type References Updated

**Problem**: Pattern referenced `sdk.Int`, `sdk.Dec`, `sdk.NewDec()` which are removed/deprecated. The codebase uses:

- `math.Int` / `math.NewInt()` from `cosmossdk.io/math` — 186+ occurrences across `x/` modules
- `math.LegacyDec` / `math.LegacyNewDec()` — 83+ occurrences across `x/` modules
- Zero occurrences of `sdk.NewInt()` or `sdk.NewDec()` in `x/` Go source (only in legacy tests via type aliases)

**Fix**: Updated all type references: `sdk.Int` → `math.Int`, `sdk.Dec` → `math.LegacyDec`.

---

## 4. Pattern 4.3 — Message Priority: Updated for ABCI 2.0

**Problem**: Pattern only discussed `CheckTx` priority. SDK v0.50 introduced ABCI 2.0 with `PrepareProposal` and `ProcessProposal` (267 occurrences in `baseapp/`), which give the block proposer direct control over transaction ordering.

**Fix**: Added `PrepareProposal`/`ProcessProposal` as the primary mechanism for transaction priority. Updated code examples.

**Evidence**: [baseapp/abci.go](cosmos-sdk/baseapp/abci.go) — `FinalizeBlock`, `PrepareProposal`, `ProcessProposal` are the ABCI 2.0 entry points. `DeliverTx` still exists internally but is called within `FinalizeBlock`.

---

## 5. Pattern 4.4 — Slow ABCI Methods: Updated Interfaces

**Problem**: Pattern used standalone `BeginBlocker(ctx sdk.Context, k keeper.Keeper)` function signatures. In SDK v0.50+, modules implement interfaces:

- `appmodule.HasBeginBlocker` — method `BeginBlock(context.Context) error`
- `appmodule.HasEndBlocker` — method `EndBlock(context.Context) error`
- Module manager calls these via [types/module/module.go:776–825](cosmos-sdk/types/module/module.go)
- `PreBlocker` is new (40 occurrences in codebase)

**Evidence**:
```
x/mint/module.go:     _ appmodule.HasBeginBlocker = AppModule{}
x/staking/module.go:  _ appmodule.HasBeginBlocker = AppModule{}
x/gov/module.go:      _ appmodule.HasEndBlocker   = AppModule{}
x/feegrant/module.go: _ appmodule.HasEndBlocker   = AppModule{}
```

**Fix**: Updated all code examples to use `func (am AppModule) BeginBlock(ctx context.Context) error` and `EndBlock` signatures. Added `PreBlock` as a new attack surface. Updated checklist.

---

## 6. Pattern 4.5 — ABCI Panics: Updated Types and Deprecated Params

**Problem**: Two sub-issues:

1. **Math types**: Pattern used `sdk.NewDec()`, `sdk.NewInt()`. Current SDK uses `math.NewInt()`, `math.LegacyNewDecFromStr()`, and panic-prone `Must*` variants like `math.LegacyMustNewDecFromStr()`.

2. **SetParamSet**: Pattern described `SetParamSet` panics. The entire `x/params` module is deprecated:
   - [x/params/module.go:61](cosmos-sdk/x/params/module.go): `"Deprecated: the params module is deprecated and will be removed in the next Cosmos SDK major release."`
   - [x/params/keeper/keeper.go:15](cosmos-sdk/x/params/keeper/keeper.go): keeper also deprecated
   - Modern modules store params directly in keeper state via `collections`

**Fix**: Updated math type references. Replaced `SetParamSet` panic pattern with direct keeper param storage pattern. Added `Must*` variant warning as a new detection pattern.

---

## 7. Pattern 4.7 — Rounding Errors: Updated Types

**Problem**: All references used `sdk.Dec`, `sdk.NewDec()`, `sdk.ZeroDec()`. These are gone.

**Evidence**: `QuoTruncate` and `QuoRoundUp` still exist on `math.LegacyDec` — [math/legacy_dec.go](cosmos-sdk/math/legacy_dec.go) (5 occurrences of QuoTruncate/QuoCeil in codebase). The vulnerability pattern itself is still valid.

**Fix**: Updated all type references to `math.LegacyDec`, `math.LegacyNewDec()`, `math.LegacyZeroDec()`.

---

## 8. Pattern 4.8 — Unregistered Handler: Marked Legacy Only

**Problem**: Pattern described `NewHandler` / `sdk.Handler` switch-case pattern. This is completely gone from the SDK:

- Zero `handler.go` files exist under `x/`
- Zero matches for `NewHandler` or `sdk.Handler` in Go files under `x/`
- All 16 modules use `msg_server.go` with protobuf service registration:
  ```
  x/auth/keeper/msg_server.go
  x/bank/keeper/msg_server.go
  x/gov/keeper/msg_server.go
  x/staking/keeper/msg_server.go
  ... (16 total)
  ```

**Fix**: Marked pattern as legacy-only (pre-v0.47). Added modern equivalent: stub/no-op `msg_server.go` implementations where a proto RPC method is technically implemented but does nothing. The Go compiler catches missing methods (unlike the old switch-case), but stub implementations are still a risk.

---

## 9. Scanning Workflow: Updated Throughout

**Changes in [SKILL.md](SKILL.md) Section 6**:

| Old | New |
|-----|-----|
| `handler.go` — Message handlers (legacy) | `keeper/msg_server.go` — Message handlers (protobuf service) |
| `abci.go` — BeginBlocker/EndBlocker | `module.go` — appmodule interface implementations |
| `types/msgs.go`, `GetSigners()` | `proto/.../tx.proto` with `cosmos.msg.v1.signer` annotations |
| `DeliverTx` | `FinalizeBlock` |
| `CheckTx` priority only | `PrepareProposal` / `ProcessProposal` / `CheckTx` |
| `sdk.Dec` / `sdk.Int` | `math.LegacyDec` / `math.Int` |

**Quick Reference Checklist** updated similarly — signer check now references proto annotations, ABCI check includes PreBlock, testing uses `FinalizeBlock`.

---

## Files Modified

- [SKILL.md](SKILL.md) — Full rewrite of sections 3, 5, 6, 7, 9, 10, 11
- [resources/VULNERABILITY_PATTERNS.md](resources/VULNERABILITY_PATTERNS.md) — All 9 patterns updated

## Validation Method

Each pattern was validated against the cosmos-sdk codebase against `cosmos-sdk` (v0.53.x, commit `82fcb05ceb`) using grep/glob searches to confirm:
- Which interfaces/types still exist
- Which have been removed or deprecated
- What replaced them
- Occurrence counts to verify patterns are real
