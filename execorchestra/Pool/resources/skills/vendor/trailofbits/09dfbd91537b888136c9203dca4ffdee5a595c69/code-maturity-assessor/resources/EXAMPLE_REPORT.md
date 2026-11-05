## Example Output

When the assessment is complete, you'll receive a comprehensive maturity report:

```
=== CODE MATURITY ASSESSMENT REPORT ===

Project: DeFi DEX Protocol
Platform: Solidity (Ethereum)
Assessment Date: March 15, 2024
Assessor: Trail of Bits Code Maturity Framework v0.1.0

---

## EXECUTIVE SUMMARY

Overall Maturity Score: 2.7 / 4.0 (MODERATE-SATISFACTORY)

Top 3 Strengths:
✓ Comprehensive testing with 96% coverage and fuzzing
✓ Well-documented access controls with multi-sig governance
✓ Clear architectural documentation with diagrams

Top 3 Critical Gaps:
⚠ Arithmetic operations lack formal specification
⚠ No event monitoring infrastructure deployed
⚠ Centralized upgrade mechanism without timelock

Priority Recommendation:
Implement arithmetic specification document and add 48-hour timelock
to all governance operations before mainnet launch.

---

## MATURITY SCORECARD

| Category                    | Rating        | Score | Notes                           |
|-----------------------------|---------------|-------|---------------------------------|
| 1. Arithmetic               | WEAK          | 1/4   | Missing specification           |
| 2. Auditing                 | MODERATE      | 2/4   | Events present, no monitoring   |
| 3. Authentication/Access    | SATISFACTORY  | 3/4   | Multi-sig, well-documented      |
| 4. Complexity Management    | MODERATE      | 2/4   | Some functions too complex      |
| 5. Decentralization         | WEAK          | 1/4   | Centralized upgrades            |
| 6. Documentation            | SATISFACTORY  | 3/4   | Comprehensive, minor gaps       |
| 7. Transaction Ordering     | MODERATE      | 2/4   | Some MEV risks documented       |
| 8. Low-Level Manipulation   | SATISFACTORY  | 3/4   | Minimal assembly, justified     |
| 9. Testing & Verification   | STRONG        | 4/4   | Excellent coverage & techniques |

**OVERALL: 2.7 / 4.0** (Moderate-Satisfactory)

---

## DETAILED ANALYSIS

### 1. ARITHMETIC - WEAK (1/4)

**Evidence:**
✗ No arithmetic specification document found
✗ AMM pricing formula not documented (src/SwapRouter.sol:89-156)
✗ Slippage calculation lacks precision analysis
✓ Using Solidity 0.8+ for overflow protection
✓ Critical functions tested for edge cases

**Critical Gap:**
File: src/SwapRouter.sol:127
```solidity
uint256 amountOut = (reserveOut * amountIn * 997) / (reserveIn * 1000 + amountIn * 997);
```
No specification for:
- Expected liquidity depth ranges
- Precision loss analysis
- Rounding direction justification

**To Reach Moderate (2/4):**
- Create arithmetic specification document
- Document all formulas and their precision requirements
- Add explicit rounding direction comments
- Test arithmetic edge cases with fuzzing

**Files Referenced:**
- src/SwapRouter.sol:89-156
- src/LiquidityPool.sol:234-267
- src/PriceCalculator.sol:178-195

---

### 2. AUDITING - MODERATE (2/4)

**Evidence:**
✓ Events emitted for all critical operations
✓ Consistent event naming (Action + noun)
✓ Indexed parameters for filtering
✗ No off-chain monitoring infrastructure
✗ No monitoring plan documented
✗ No incident response plan

**Events Found:** 23 events across 8 contracts
- Swap, AddLiquidity, RemoveLiquidity ✓
- PairCreated, LiquidityProvided ✓
- OwnershipTransferred, GovernanceProposed ✓

**Critical Gap:**
No monitoring alerts for:
- Large swaps causing significant price impact
- Oracle price deviations
- Unusual liquidity withdrawal patterns

**To Reach Satisfactory (3/4):**
- Deploy off-chain monitoring (Tenderly/Defender)
- Create monitoring playbook document
- Set up alerts for critical events
- Test incident response plan quarterly

---

### 3. AUTHENTICATION/ACCESS CONTROLS - SATISFACTORY (3/4)

**Evidence:**
✓ All privileged functions have access controls
✓ Multi-sig (3/5) controls governance
✓ Role separation (Admin, Operator, Pauser)
✓ Roles documented in ROLES.md
✓ Two-step ownership transfer
✓ All access patterns tested
✓ Emergency pause by separate role

**Access Control Implementation:**
- OpenZeppelin AccessControl used consistently
- 4 roles defined with non-overlapping privileges
- Emergency functions require multi-sig

**Minor Gap:**
Multi-sig is EOA-based (should upgrade to Governor contract)

**To Reach Strong (4/4):**
- Replace multi-sig EOAs with on-chain Governor
- Add timelock to all parameter changes
- Document key compromise scenarios
- Test governor upgrade path

**Files Referenced:**
- All contracts use consistent access patterns
- ROLES.md comprehensive
- test/access/* covers all scenarios

---

### 9. TESTING & VERIFICATION - STRONG (4/4)

**Evidence:**
✓ 96% line coverage, 94% branch coverage
✓ 287 unit tests, all passing
✓ Echidna fuzzing for 12 invariants
✓ Integration tests for all workflows
✓ Mutation testing implemented
✓ Tests run in CI/CD
✓ Fork tests against mainnet state

**Testing Breakdown:**
- Unit: 287 tests (forge test)
- Integration: 45 scenarios (end-to-end flows)
- Fuzzing: 12 invariants (Echidna, 10k runs each)
- Formal: 3 key properties (Certora)
- Fork: Tested against live Uniswap/SushiSwap

**Uncovered Code:**
- Emergency migration (tested manually)
- Governance upgrade path (one-time)

**Why Strong:**
Exceeds all satisfactory criteria with formal verification and
extensive fuzzing. Test quality is exceptional.

---

## IMPROVEMENT ROADMAP

### CRITICAL (Fix Before Mainnet - Week 1-2)

**1. Create Arithmetic Specification [HIGH IMPACT]**
- Effort: 3-5 days
- Document all formulas with ground-truth models
- Analyze precision loss for each operation
- Justify rounding directions
- Impact: Moves Arithmetic from WEAK → MODERATE

**2. Add Governance Timelock [HIGH IMPACT]**
- Effort: 2-3 days
- Deploy TimelockController (48-hour delay)
- Update all governance functions
- Document emergency override procedure
- Impact: Moves Decentralization from WEAK → MODERATE

---

### HIGH PRIORITY (Fix Before Launch - Week 3-4)

**3. Deploy Monitoring Infrastructure [MEDIUM IMPACT]**
- Effort: 3-4 days
- Set up Tenderly/OpenZeppelin Defender
- Create alert rules for critical events
- Document monitoring playbook
- Impact: Moves Auditing from MODERATE → SATISFACTORY

**4. Simplify Complex Functions [MEDIUM IMPACT]**
- Effort: 5-7 days
- Split SwapRouter.getAmountOut() (cyclomatic complexity: 15)
- Extract PriceCalculator._validateSlippage() logic
- Impact: Moves Complexity from MODERATE → SATISFACTORY

---

### MEDIUM PRIORITY (Improve for V2 - Month 2-3)

**5. Document MEV Risks**
- Effort: 2-3 days
- Create MEV analysis document
- Add slippage protection where missing
- Impact: Moves Transaction Ordering from MODERATE → SATISFACTORY

**6. Upgrade to On-Chain Governance**
- Effort: 1-2 weeks
- Replace multi-sig with Governor contract
- Add voting period and quorum
- Impact: Moves Authentication from SATISFACTORY → STRONG

---

## CONCLUSION

The codebase demonstrates **MODERATE-SATISFACTORY maturity** (2.7/4.0),
with excellent testing practices and good documentation. Primary concerns
are arithmetic specification gaps and centralized upgrade control.

**Recommended Path to Mainnet:**
1. Complete CRITICAL items (arithmetic spec, timelock)
2. Address HIGH priority items (monitoring, complexity)
3. Conduct external audit
4. Launch with documented limitations
5. Implement MEDIUM priority items in V2

**Timeline:** 3-4 weeks to address critical/high items before audit.

---

Assessment completed using Trail of Bits Building Secure Contracts
Code Maturity Evaluation Framework v0.1.0
```
