# Report Templates

This document contains report templates and deliverables formats for token integration analysis.

---

## 1. Compliance Checklist

**General Considerations**:
- [x/☐] Security review completed
- [x/☐] Team contactable
- [x/☐] Security mailing list exists

**Contract Composition**:
- [x/☐] Avoids unnecessary complexity
- [x/☐] Uses SafeMath / Solidity 0.8+
- [x/☐] Few non-token functions
- [x/☐] Single address entry point

**Owner Privileges**:
- [x/☐] Not upgradeable / risks understood
- [x/☐] Limited minting
- [x/☐] Not pausable / risks understood
- [x/☐] No blacklist / risks understood
- [x/☐] Known team

**ERC20 Conformity** (if applicable):
- [x/☐] Returns boolean from transfer functions
- [x/☐] Metadata functions present
- [x/☐] Decimals returns uint8
- [x/☐] Race condition mitigated
- [x/☐] Passes slither-check-erc
- [x/☐] No external calls in transfers
- [x/☐] No transfer fees
- [x/☐] Interest accounted for

**Token Scarcity** (if applicable):
- [x/☐] Distributed ownership
- [x/☐] Sufficient total supply
- [x/☐] Multiple exchange listings
- [x/☐] Flash loan risks understood
- [x/☐] No flash minting / risks understood

**ERC721 Conformity** (if applicable):
- [x/☐] Transfers to 0x0 revert
- [x/☐] safeTransferFrom implemented
- [x/☐] Metadata functions handled
- [x/☐] ownerOf reverts properly
- [x/☐] Transfers clear approvals
- [x/☐] Token IDs immutable
- [x/☐] onERC721Received protected
- [x/☐] Safe minting implemented
- [x/☐] Burning clears approvals

---

## 2. Weird Token Pattern Analysis

For each applicable pattern:
- **Pattern name**
- **Presence**: Found / Not Found
- **Risk level**: Critical / High / Medium / Low
- **Evidence**: File:line references
- **Mitigation**: Recommendations

---

## 3. On-chain Analysis Report

(If deployed contract analyzed)

**Token Information**:
- Name, Symbol, Decimals
- Total Supply
- Contract address(es)

**Holder Distribution**:
- Total holders
- Top 10 holder percentage
- Concentration risk

**Exchange Distribution**:
- Listings on major DEXs
- Liquidity concentration
- Single point of failure risk

**Configuration**:
- Owner/admin address
- Pause status
- Upgrade configuration
- Minting caps

---

## 4. Integration Safety Assessment

(If analyzing protocol integrating tokens)

**Safe Transfer Usage**:
- SafeERC20 library usage
- Return value checking
- Balance verification

**Defensive Patterns**:
- Reentrancy protection
- Fee-on-transfer handling
- Zero value handling
- Allowlist implementation

**Weird Token Handling**:
- Missing returns handled
- Fee-on-transfer protected
- Rebase-safe accounting
- Blocklist-aware design

---

## 5. Prioritized Recommendations

**CRITICAL** (fix before deployment):
- Missing return value checks
- Reentrancy vulnerabilities
- Unsafe transfer patterns
- ERC non-conformities causing loss

**HIGH** (fix soon):
- Fee-on-transfer mishandling
- Rebase token incompatibility
- Insufficient scarcity safeguards
- Owner privilege risks

**MEDIUM** (improve security):
- Upgrade detection
- Allowlist implementation
- Better defensive patterns
- Zero value handling

**LOW** (best practices):
- Additional Slither checks
- Property-based testing
- Documentation improvements
