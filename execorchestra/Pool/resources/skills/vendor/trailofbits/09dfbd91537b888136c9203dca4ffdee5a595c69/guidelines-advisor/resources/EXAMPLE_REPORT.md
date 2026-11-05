## Example Output

When the analysis is complete, you'll receive comprehensive guidance like this:

```
=== DEVELOPMENT GUIDELINES ANALYSIS ===

Project: NFT Marketplace
Platform: Solidity (Ethereum)
Analysis Date: March 15, 2024

---

## 1. DOCUMENTATION & SPECIFICATIONS

### Generated System Description

**Plain English Overview:**
The NFT Marketplace allows users to list, buy, and auction ERC721 tokens.
The system uses a decentralized orderbook where sellers create listings with
price and duration. Buyers can purchase instantly or place bids for auctions.
A 2.5% platform fee is collected on each sale.

**Key Assumptions:**
- All NFTs follow ERC721 standard
- Prices denominated in ETH only
- No token whitelisting (any ERC721 accepted)
- Platform fee immutable after deployment

### Architectural Diagrams Generated

✓ contract-interactions.png - Shows Marketplace, OrderBook, FeeCollector flow
✓ state-machine.png - Listing states (Created → Active → Sold/Cancelled/Expired)
✓ auction-flow.png - Bid placement and finalization sequence

### Documentation Gaps Identified

⚠ Missing NatSpec:
- OrderBook.cancelOrder() - No @notice or @param
- FeeCollector.withdrawFees() - Missing @dev implementation notes

⚠ Undocumented Assumptions:
- What happens if NFT transfer fails during purchase?
- Are listings automatically cleaned up after expiration?
- Fee distribution mechanism not explained

**Recommendation:** Add comprehensive NatSpec to all public functions
and document error handling for external calls.

---

## 2. ARCHITECTURE ANALYSIS

### On-Chain vs Off-Chain Components

**Current Distribution:**
- On-Chain: Listing creation, order execution, fee collection
- Off-Chain: Order discovery, price indexing, user notifications

**Optimization Opportunities:**
✓ Order matching is efficient (on-chain orderbook)
✗ Listing enumeration is gas-intensive

**Recommendation:**
Consider moving listing discovery off-chain using event indexing.
Keep core execution on-chain. Estimated gas savings: 40% for browse operations.

### Upgradeability Review

**Current Pattern:** TransparentUpgradeableProxy (OpenZeppelin)

**Assessment:**
✓ Proxy and implementation use shared storage base
✓ Initialization properly handled
✓ No function shadowing detected
✗ No timelock on upgrades (admin can upgrade immediately)

**Critical Issue:**
File: contracts/Marketplace.sol
The marketplace uses delegatecall proxy but admin is EOA without timelock.

**Recommendation:**
- Deploy TimelockController (48-hour delay)
- Transfer proxy admin to timelock
- Add emergency pause for critical bugs

### Proxy Pattern Security

**Findings:**
✓ Storage layout consistent (inherits MarketplaceStorage)
✓ No constructors in implementation
✓ Initialize function has initializer modifier
⚠ Immutable variables in proxy (PLATFORM_FEE)

**Issue:** PLATFORM_FEE defined as immutable in proxy will not update
if implementation changes this value.

**Fix:** Move PLATFORM_FEE to storage or accept it's immutable forever.

---

## 3. IMPLEMENTATION REVIEW

### Function Composition

**Complex Functions Identified:**
⚠ executePurchase() - 45 lines, cyclomatic complexity: 12
  - Handles payment, NFT transfer, fee calc, event emission
  - Recommendation: Extract _validatePurchase(), _processPayment(), _transferNFT()

⚠ finalizeAuction() - 38 lines, cyclomatic complexity: 10
  - Multiple nested conditionals for winner determination
  - Recommendation: Extract _determineWinner(), _refundLosers()

✓ Other functions well-scoped (average 15 lines)

### Inheritance

**Hierarchy Analysis:**
```
Marketplace
├─ Ownable
├─ ReentrancyGuard
├─ Pausable
└─ MarketplaceStorage
```

✓ Shallow inheritance (depth: 2)
✓ No diamond problem
✓ Clear separation of concerns

**Slither Inheritance Graph:** contracts/inheritance.png (generated)

### Events

**Event Coverage:**
✓ 12 events defined
✓ All state changes emit events
✓ Consistent naming (ListingCreated, OrderFulfilled, BidPlaced)
✓ Indexed parameters for filtering (tokenId, seller, buyer)

⚠ Missing Events:
- Platform fee updates (if ever made variable)
- Pause/unpause operations

**Recommendation:** Add PlatformPaused/Unpaused events for monitoring.

### Common Pitfalls

**Issues Found:**

❌ CRITICAL: Reentrancy in executePurchase()
File: contracts/Marketplace.sol:234
```solidity
function executePurchase(uint256 listingId) external payable {
    Listing memory listing = listings[listingId];
    IERC721(listing.nftContract).transferFrom(listing.seller, msg.sender, listing.tokenId);
    // State update AFTER external call!
    listing.status = Status.Sold;
}
```
**Fix:** Follow checks-effects-interactions. Update state before external calls.

⚠ HIGH: Unvalidated external call return
File: contracts/Marketplace.sol:245
```solidity
payable(seller).transfer(amount);  // Can fail silently
```
**Fix:** Use call{value}() and check return value or use Address.sendValue().

✓ No timestamp dependence
✓ No tx.origin usage
✓ Integer overflow protected (Solidity 0.8+)

---

## 4. DEPENDENCIES

**Current Dependencies:**
✓ @openzeppelin/contracts@4.9.0 - Well-tested, good choice
✗ Custom ERC721 implementation (contracts/CustomERC721.sol)

**Issues:**
⚠ CustomERC721 reinvents OpenZeppelin's ERC721
   - 234 lines of duplicate code
   - No added functionality
   - Increases audit surface

**Recommendation:**
Replace CustomERC721 with OpenZeppelin's implementation.
Saves 234 lines, reduces risk, improves maintainability.

**Dependency Management:**
✓ Using npm for dependencies
✓ Package versions pinned
⚠ Dependencies not updated in 8 months

**Action:** Update @openzeppelin/contracts to latest 5.x (breaking changes, test thoroughly)

---

## 5. TESTING EVALUATION

**Current Test Suite:**
- 45 unit tests (forge test)
- 12 integration tests
- Coverage: 78%

**Gaps Identified:**
✗ No fuzzing (Echidna/Foundry)
✗ No formal verification
✗ Edge cases not covered:
  - Auction with zero bids
  - Listing with expired timestamp
  - Purchase during contract pause

**Recommendations:**
1. Add Foundry invariant tests:
   - Total fees collected == sum of individual sales * 0.025
   - Active listings count matches actual active listings
   - No NFT can be in multiple active listings

2. Increase coverage to 95%+ by testing:
   - Pausable functions during pause state
   - Reentrancy attack scenarios
   - Failed NFT transfers

3. Add integration tests:
   - End-to-end auction flow with multiple bidders
   - Platform fee collection and withdrawal
   - Upgrade and data migration

**Estimated Effort:** 1-2 weeks to reach 95% coverage with invariant testing

---

## PRIORITIZED RECOMMENDATIONS

### CRITICAL (Fix Immediately)
1. **Fix reentrancy in executePurchase()** [HIGH IMPACT]
   - Risk: Funds can be drained
   - Effort: 1 day
   - File: contracts/Marketplace.sol:234

2. **Validate external call returns** [HIGH IMPACT]
   - Risk: Failed transfers not detected
   - Effort: 1 day
   - Files: Multiple payment operations

3. **Add timelock to upgrades** [HIGH IMPACT]
   - Risk: Instant malicious upgrade
   - Effort: 2 days

### HIGH (Before Mainnet)
4. **Remove CustomERC721, use OpenZeppelin** [MEDIUM IMPACT]
   - Benefit: Reduce code, increase security
   - Effort: 3 days

5. **Increase test coverage to 95%** [MEDIUM IMPACT]
   - Benefit: Catch edge case bugs
   - Effort: 1-2 weeks

6. **Add comprehensive NatSpec** [LOW IMPACT]
   - Benefit: Better documentation
   - Effort: 2-3 days

### MEDIUM (Post-Launch V2)
7. **Optimize listing enumeration** [MEDIUM IMPACT]
   - Benefit: 40% gas savings on reads
   - Effort: 1 week

8. **Add invariant fuzzing** [HIGH IMPACT]
   - Benefit: Discover hidden bugs
   - Effort: 1 week

---

## SUMMARY

**Overall Assessment:** MODERATE MATURITY

The codebase follows many best practices with good use of OpenZeppelin
libraries and clear architecture. Critical issues are reentrancy vulnerability
and lack of upgrade timelock. Testing needs improvement.

**Path to Production:**
1. Fix CRITICAL items (reentrancy, timelock) - Week 1
2. Address HIGH items (dependencies, testing) - Week 2-3
3. External audit - Week 4-5
4. Mainnet deployment with documented limitations
5. MEDIUM items in V2 - Month 2-3

**Estimated Timeline:** 3-4 weeks to production-ready state.

---

Analysis completed using Trail of Bits Development Guidelines
```
