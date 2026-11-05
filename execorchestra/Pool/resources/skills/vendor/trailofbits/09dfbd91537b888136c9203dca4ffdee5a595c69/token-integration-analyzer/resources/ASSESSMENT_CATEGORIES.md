# Assessment Categories Reference

This document contains detailed assessment criteria for token analysis. Each category includes what to check, analysis methods, and verification checklists.

---

## 1. GENERAL CONSIDERATIONS

**What I'll check**:
- Security review history
- Team contacts and transparency
- Security mailing list existence

**I'll ask you**:
- Has this token been audited?
- Is the team contactable?
- Is there a security mailing list?

**Best practices**:
- Interact only with reviewed tokens
- Maintain contact with token teams
- Subscribe to security announcements

---

## 2. CONTRACT COMPOSITION

**What I'll analyze**:

**Complexity**:
- Overall contract complexity
- Lines of code
- Inheritance depth
- Function count
- Use Slither's `human-summary` printer

**SafeMath Usage** (pre-0.8 Solidity):
- Arithmetic operations protection
- Unchecked blocks justification

**Non-token Functions**:
- Functions beyond standard ERC interface
- Unnecessary complexity
- Use Slither's `contract-summary` printer

**Single Address Entry Point**:
- Multiple addresses pointing to same token
- Proxy patterns that create multiple entry points

**Checks**:
- [ ] Contract avoids unnecessary complexity
- [ ] Contract uses SafeMath or Solidity 0.8+ (for Solidity)
- [ ] Contract has only a few non-token-related functions
- [ ] Token has only one address entry point

---

## 3. OWNER PRIVILEGES

**What I'll check**:

**Upgradeability**:
- Proxy patterns (UUPS, Transparent, Beacon)
- Implementation change mechanisms
- Use Slither's `human-summary` printer

**Minting Capabilities**:
- Unlimited vs limited minting
- Minting access controls
- Total supply caps

**Pausability**:
- Pause mechanisms
- Who can pause
- Impact on existing holders

**Blacklisting**:
- Blocklist functionality
- Admin controls
- USDC/USDT-style blocklists

**Team Transparency**:
- Known team members
- Legal jurisdiction
- Accountability

**Checks**:
- [ ] Token is not upgradeable (or upgrade risks understood)
- [ ] Owner has limited minting capabilities
- [ ] Token is not pausable (or pause risks understood)
- [ ] Owner cannot blacklist addresses (or risks understood)
- [ ] Team is known and accountable

---

## 4. ERC20 CONFORMITY CHECKS

**What I'll analyze**:

**Return Values**:
- `transfer` returns bool
- `transferFrom` returns bool
- Missing returns (USDT, BNB, OMG pattern)
- False returns (Tether Gold pattern)

**Function Presence**:
- `name`, `decimals`, `symbol` existence
- Optional functions handling

**Decimals Type**:
- Returns `uint8`
- Value below 255
- Low decimals (USDC: 6, Gemini USD: 2)
- High decimals (YAM-V2: 24)

**Race Condition Mitigation**:
- ERC20 approve race condition
- Increase/decrease allowance pattern
- USDT/KNC approval protection

**Slither Tools**:
- Run `slither-check-erc` for automated checks
- Run `slither-prop` to generate properties

**Checks**:
- [ ] `transfer` and `transferFrom` return boolean
- [ ] `name`, `decimals`, `symbol` present if used
- [ ] `decimals` returns `uint8` with value < 255
- [ ] Token mitigates ERC20 race condition
- [ ] Contract passes `slither-check-erc` tests
- [ ] Contract passes `slither-prop` generated tests

---

## 5. ERC20 EXTENSION RISKS

**What I'll check**:

**External Calls in Transfers**:
- ERC777 hooks
- Reentrancy risks
- `tokensReceived` callbacks
- Check for: Amp (AMP), imBTC patterns

**Transfer Fees**:
- Deflationary tokens
- Fee-on-transfer (STA, PAXG)
- Future fee risks (USDT, USDC can add fees)
- Balance checks after transfer

**Interest/Yield Bearing**:
- Rebasing tokens (Ampleforth)
- Airdropped governance tokens
- Compound-style interest
- Cached balance issues

**Checks**:
- [ ] Token is not ERC777 or has no external calls in transfer
- [ ] `transfer`/`transferFrom` do not take fees
- [ ] Interest earned from token is accounted for

---

## 6. TOKEN SCARCITY ANALYSIS

**What I'll do**:

For deployed tokens, I'll query on-chain data using web3/ethers:

**Supply Distribution**:
```javascript
// Query holder distribution
// Check top 10 holders percentage
// Identify concentration risk
```

**Total Supply**:
```javascript
// Query totalSupply
// Check if sufficient for manipulation resistance
// Identify low supply risk
```

**Exchange Distribution**:
```javascript
// Query balance on major DEXs/CEXs
// Check if tokens concentrated in one exchange
// Identify single point of failure
```

**Flash Loan Risk**:
- Large fund attack potential
- Flash loan availability for this token

**Flash Minting**:
- Flash mint functions (DAI-style)
- Maximum mintable amount
- Overflow risks

**Checks**:
- [ ] Supply owned by more than a few users
- [ ] Total supply is sufficient
- [ ] Tokens located in more than a few exchanges
- [ ] Flash loan/large fund risks understood
- [ ] Token does not allow flash minting (or risks understood)

**Note**: I'll only perform on-chain analysis if you provide a contract address. Won't hallucinate if not applicable.

---

## 7. WEIRD ERC20 PATTERNS

I'll check for all 20+ known weird token patterns:

### 7.1 Reentrant Calls
- ERC777 tokens with hooks
- Transfer callbacks
- Historical exploits: imBTC Uniswap, lendf.me

**Tokens**: Amp (AMP), imBTC

### 7.2 Missing Return Values
- No bool return on transfer/transferFrom
- Some methods return, others don't
- False returns on success (Tether Gold)

**Tokens**: USDT, BNB, OMG, Tether Gold

### 7.3 Fee on Transfer
- Transfer fees (STA, PAXG)
- Future fee capability (USDT, USDC)
- Deflationary mechanics

**Exploit**: Balancer STA hack ($500k)

### 7.4 Balance Modifications Outside Transfers
- Rebasing tokens (Ampleforth)
- Governance airdrops (Compound)
- Mintable/burnable by admin
- Cached balance risks

### 7.5 Upgradable Tokens
- USDC, USDT upgradeability
- Logic change risks
- Freeze integration on upgrade

### 7.6 Flash Mintable
- DAI flash mint module
- `type(uint256).max` supply risk
- One-transaction minting

### 7.7 Blocklists
- USDC, USDT blocklists
- Admin-controlled blocking
- Contract trap risk
- Regulatory/extortion risk

### 7.8 Pausable Tokens
- BNB, ZIL pause functionality
- Admin pause risk
- User fund trap

### 7.9 Approval Race Protections
- USDT, KNC approval restrictions
- Cannot approve M > 0 when N > 0 approved
- Integration issues

### 7.10 Revert on Approval to Zero Address
- OpenZeppelin pattern
- `approve(address(0), amt)` reverts
- Special case handling needed

### 7.11 Revert on Zero Value Approvals
- BNB pattern
- `approve(address, 0)` reverts
- Approval reset issues

### 7.12 Revert on Zero Value Transfers
- LEND pattern
- Zero amount transfers fail
- Edge case handling

### 7.13 Multiple Token Addresses
- Proxied tokens with multiple addresses
- Address-based tracking broken
- Rescue function exploits

### 7.14 Low Decimals
- USDC: 6 decimals
- Gemini USD: 2 decimals
- Precision loss amplified

### 7.15 High Decimals
- YAM-V2: 24 decimals
- Overflow risks
- Liveness issues

### 7.16 transferFrom with src == msg.sender
- DSToken: no allowance decrease
- OpenZeppelin: always decrease
- Different semantics

### 7.17 Non-string Metadata
- MKR: bytes32 name/symbol
- Metadata consumption issues
- Type casting needed

### 7.18 Revert on Transfer to Zero Address
- OpenZeppelin pattern
- Burn mechanism broken
- Zero address handling

### 7.19 No Revert on Failure
- ZRX, EURS pattern
- Returns false instead of reverting
- Forgotten require wrapping

### 7.20 Revert on Large Approvals
- UNI, COMP: max uint96
- uint256(-1) special case
- Allowance mapping mismatch

### 7.21 Code Injection via Token Name
- Malicious JavaScript in name
- Frontend exploits
- Etherdelta hack pattern

### 7.22 Unusual Permit Function
- DAI, RAI, GLM non-EIP2612 permit
- No revert on unsupported permit
- Phantom function execution

### 7.23 Transfer Less Than Amount
- cUSDCv3 type(uint256).max handling
- Only balance transferred
- Vault accounting broken

### 7.24 ERC-20 Native Currency Representation
- Celo: CELO token
- Polygon: POL token
- zkSync Era: ETH token
- Double spending risks

**Exploit**: Uniswap V4 critical vulnerability

**For each pattern I'll**:
- Search for implementation
- Assess risk level
- Check integration safety
- Provide mitigation strategies

---

## 8. TOKEN INTEGRATION SAFETY

**If analyzing a protocol that integrates tokens**:

**What I'll check**:

**Safe Transfer Pattern**:
```solidity
// Check for proper transfer handling
// Verify return value checking
// Look for SafeERC20 usage
```

**Balance Verification**:
```solidity
// Check balance before and after
// Don't assume transfer amount = actual amount
// Fee-on-transfer protection
```

**Allowlist Pattern**:
```solidity
// Contract-level allowlist
// Known good tokens
// UI-level filtering
```

**Wrapper Contracts**:
```solidity
// Edge wrappers for external tokens
// Consistent internal semantics
// Isolation of weird behavior
```

**Defensive Patterns**:
- Reentrancy guards on token interactions
- Balance caching strategies
- Upgrade detection mechanisms
- Zero value handling
- Return value verification

---

## 9. ERC721 CONFORMITY CHECKS

**What I'll analyze**:

**Transfer to 0x0**:
- Should revert per standard
- Burning mechanism
- Token loss prevention

**safeTransferFrom Implementation**:
- Correct signature
- onERC721Received callback
- NFT loss to contracts

**Metadata Functions**:
- `name`, `symbol` presence
- Can return empty string
- `decimals` returns `uint8(0)` if present

**ownerOf Behavior**:
- Reverts for invalid tokenId
- Reverts for burned tokens
- Never returns 0x0

**Transfer Clears Approvals**:
- Per standard requirement
- Approval state management

**Token ID Immutability**:
- ID cannot change during lifetime
- Per standard requirement

**Checks**:
- [ ] Transfers to 0x0 revert
- [ ] `safeTransferFrom` implemented correctly
- [ ] `name`, `symbol` present if used
- [ ] `decimals` returns `uint8(0)` if present
- [ ] `ownerOf` reverts for invalid/burned tokens
- [ ] Transfers clear approvals
- [ ] Token IDs immutable during lifetime

---

## 10. ERC721 COMMON RISKS

**What I'll check**:

**onERC721Received Callback**:
- Reentrancy via callback
- safeMint risks
- External call ordering

**Safe Minting to Contracts**:
- Minting functions behave like `safeTransferFrom`
- Prevent NFT loss to contracts
- Handle contract recipients

**Burning Clears Approvals**:
- Burn function existence
- Approval clearing
- Approval state after burn

**Checks**:
- [ ] `onERC721Received` callback reentrancy protected
- [ ] NFTs safely minted to smart contracts
- [ ] Burning tokens clears approvals

---

## Slither Integration

### Commands I'll Help Run

**ERC Conformity Check**:
```bash
# For ERC20
slither-check-erc [address-or-path] TokenName --erc erc20

# For ERC721
slither-check-erc [address-or-path] TokenName --erc erc721
```

**Contract Analysis**:
```bash
# Human-readable summary (complexity, upgrades, etc.)
slither [target] --print human-summary

# Function and modifier summary
slither [target] --print contract-summary
```

**Property Generation**:
```bash
# Generate test properties for Echidna/Manticore
slither-prop . --contract TokenName
```

**Note**: I'll adapt based on whether tools are available. I can work without Slither but recommend using it for Solidity projects.

---

## On-chain Analysis Integration

### Querying Deployed Contracts

If you provide a contract address, I can query on-chain data:

**Setup**:
```javascript
// I'll use web3.js or ethers.js
const Web3 = require('web3');
const web3 = new Web3('RPC_URL');
```

**Token Information**:
```javascript
// Query basic info
const name = await token.methods.name().call();
const symbol = await token.methods.symbol().call();
const decimals = await token.methods.decimals().call();
const totalSupply = await token.methods.totalSupply().call();
```

**Holder Analysis**:
```javascript
// Query top holders
// Calculate concentration
// Identify whale risk
```

**Exchange Analysis**:
```javascript
// Query balances on Uniswap, Curve, etc.
// Check centralization in single exchange
```

**Configuration**:
```javascript
// Query owner/admin
// Check pause status
// Verify upgrade configuration
```

**Note**: I'll only perform on-chain queries if you provide an address and RPC endpoint. Won't hallucinate if not applicable.

---

## Known Non-Standard Tokens Database

I have comprehensive knowledge of known non-standard tokens:

### Missing Revert
- Basic Attention Token (BAT)
- Huobi Token (HT)
- Compound USD Coin (cUSDC)
- 0x Protocol Token (ZRX)

### Transfer Hooks (Reentrant)
- Amp (AMP)
- The Tokenized Bitcoin (imBTC)

### Missing Return Data
- Binance Coin (BNB) - only on `transfer`
- OMGToken (OMG)
- Tether USD (USDT)

### Permit No-op
- Wrapped Ether (WETH)

### Additional Non-Standard
- USDC: upgradeable, 6 decimals
- DAI: non-standard permit, flash mintable
- UNI, COMP: revert on large approvals (>= 2^96)

I'll check if your codebase interacts with any of these and verify proper handling.
