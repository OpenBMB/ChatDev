---
name: cosmos-vulnerability-scanner
description: "Scans Cosmos SDK blockchain modules and CosmWasm contracts for consensus-critical vulnerabilities — chain halts, fund loss, state divergence. 25 core + 16 IBC + 10 EVM + 3 CosmWasm patterns. Use when auditing custom x/ modules, reviewing IBC integrations, or assessing pre-launch chain security. Updated for SDK v0.53.x."
---

# Cosmos Vulnerability Scanner

## Purpose

Scan Cosmos SDK modules and CosmWasm contracts for vulnerabilities that cause chain halts, consensus failures, or fund loss. Spawns parallel scanning agents — each specializing in a vulnerability category — that return findings to the main skill, which then writes them as individual markdown files to an output directory.

**Output directory**: defaults to `.bughunt_cosmos/`. If the user specifies a different directory in their prompt, use that instead.

## When to Use

- Auditing Cosmos SDK modules (custom `x/` modules)
- Reviewing CosmWasm smart contracts
- Pre-launch security assessment of Cosmos chains
- Investigating chain halt incidents

## When NOT to Use

- Pure Solidity/EVM audits without Cosmos SDK — use Solidity-specific tools
- CometBFT consensus engine internals — this covers SDK modules, not the consensus layer itself
- General Go code review with no blockchain context
- Cosmos SDK application logic that is not consensus-critical (e.g., CLI commands, REST endpoints)
- CosmWasm contract-only audits on chains without custom SDK modules — use the CosmWasm checklist items alone

## Essential Principles

1. **Consensus path is king** — A bug only matters for chain halt/fund loss if it's on the consensus-critical execution path (BeginBlock, EndBlock, FinalizeBlock, msg_server handlers, AnteHandler). Always verify a finding is reachable from consensus before reporting it.
2. **State divergence = chain halt** — Any non-determinism that causes validators to compute different state roots will halt the chain. This is the highest-severity class because it affects all validators simultaneously.
3. **Check the version** — Cosmos SDK has breaking changes across major versions (v0.47 removed GetSigners, v0.50 added ABCI 2.0, v0.53 deprecated ValidateBasic). Always check `go.mod` versions before applying patterns.
4. **False positives waste audit time** — A map iteration in a CLI command is not a consensus bug. A panic in a query handler does not halt the chain. Verify the execution context before flagging.
5. **Cross-module interactions are where bugs hide** — The most severe findings (IBC reentrancy, EVM/Cosmos state desync, authz escalation) involve interactions between modules, not bugs within a single module.

## Scanning Workflow

### Phase 1: Discovery (synchronous)

**Entry**: Target codebase path provided by user. Codebase contains Go source (e.g., `x/` modules, `go.mod`) or Rust contracts with `cosmwasm_std`.

Run a **synchronous subagent** (Agent tool) with the full contents of [DISCOVERY.md](resources/DISCOVERY.md) as its prompt. The agent must:

1. Follow the Discovery workflow to explore the target codebase
2. Return the full CLAUDE.md content (the technical inventory and threat model) in its response
3. Return a structured summary with exactly these fields:

```
PLATFORM: pure-cosmos | evm | wasm        (pick one; if multiple, comma-separated)
IBC_ENABLED: true | false
SDK_VERSION: <version from go.mod>
IBC_GO_VERSION: <version from go.mod, or "n/a">
CUSTOM_MODULES: <comma-separated list of x/* modules>
```

After the subagent returns, **you** (the main skill) Write the CLAUDE.md to the target repo root. Save its path and the discovery values — these feed into Phase 2.

**Exit**: CLAUDE.md written by main skill. PLATFORM, IBC_ENABLED, SDK_VERSION, IBC_GO_VERSION, and CUSTOM_MODULES captured.

### Phase 2: Parallel Vulnerability Scan

Spawn scanning agents **in a single message** for maximum parallelism. Use the Agent Prompt Template below, filling in the reference file for each agent. Subagents only need read access (Grep, Glob, Read) — they return findings in their response and the main skill writes the files.

**Always spawn these 3 agents:**

| Agent Name | Reference File | Scope |
|------------|---------------|-------|
| `core-scanner` | `VULNERABILITY_PATTERNS.md` | §1-9: non-determinism, ABCI, signers, validation, handlers, ante security |
| `state-scanner` | `STATE_VULNERABILITY_PATTERNS.md` | §11-23: bookkeeping, bank, pagination, events, tx replay, governance, arithmetic, encoding, deprecated modules |
| `advanced-scanner` | `ADVANCED_VULNERABILITY_PATTERNS.md` | §24-27: storage keys, consensus validation, circuit breaker, crypto |

**Spawn conditionally (in the same parallel message):**

| Agent Name | Condition | Reference File |
|------------|-----------|---------------|
| `evm-scanner` | PLATFORM includes `evm` | `EVM_VULNERABILITY_PATTERNS.md` |
| `ibc-scanner` | IBC_ENABLED is `true` | `IBC_VULNERABILITY_PATTERNS.md` |
| `cosmwasm-scanner` | PLATFORM includes `wasm` | `COSMWASM_VULNERABILITY_PATTERNS.md` |

#### Agent Prompt Template

Construct each agent's prompt by replacing `{REFERENCE_FILE_PATH}` with the full path to the reference file (under `{baseDir}/resources/`) and `{CLAUDE_MD_PATH}` with the path to the CLAUDE.md written in Phase 1:

~~~
Perform a very thorough security scan of a Cosmos SDK codebase for specific vulnerability patterns.

CONTEXT:
Read {CLAUDE_MD_PATH} for codebase context (SDK version, modules, threat model, key files).

PATTERNS:
Read {REFERENCE_FILE_PATH} — it contains numbered vulnerability patterns. For EACH pattern:
1. Read the detection patterns and "What to Check" items
2. Use Grep and Glob to search the target codebase for each pattern
3. When a match is found, Read surrounding code to verify it's on a consensus-critical path (BeginBlock, EndBlock, FinalizeBlock, msg_server handlers, AnteHandler)
4. Classify severity per the guidelines below

RULES:
- Consensus path only: Only flag code reachable from consensus-critical execution. CLI/query/test code is NOT a finding.
- Check SDK version in go.mod before applying patterns (v0.47 removed GetSigners, v0.50 added ABCI 2.0, v0.53 deprecated ValidateBasic).
- Always use the Grep tool for searches, not bash grep. The reference file contains search patterns — use them directly with the Grep tool.
- Ignore cross-references to other resource files (e.g., links to IBC or COSMWASM patterns). Those patterns are covered by other scanning agents.
- Reject these rationalizations:
  - "ValidateBasic catches this" — deprecated and facultative since SDK v0.53
  - "Behind governance, so safe" — governance proposals can be malicious
  - "IBC counterparty is trusted" — any chain can open a channel
  - "Panic can't happen, input is validated" — trace the full call chain
  - "Rounding error is only a few tokens" — compounds over time, can be looped
  - "EVM precompile handles rollback" — many have incomplete rollback

SEVERITY:
- Critical (fund loss): signer mismatch, broken bookkeeping, AnteHandler bypass, bank keeper misuse, IBC token inflation, EVM/Cosmos desync, Merkle proof forgery, arithmetic overflow
- High (chain halt): non-determinism, ABCI panics, slow ABCI, non-deterministic IBC acks, consensus gaps, CacheContext event leak
- Medium (DoS): unbounded pagination, tx replay, missing validation, governance spam, rate limiting, circuit breaker bypass, storage key collisions
- Low (logic): rounding errors, stub handlers, event override, module ordering

OUTPUT — RETURN FORMAT:
Do NOT write any files. Return ALL findings and the summary in your response.

For each pattern, return one of:
  §NUM PATTERN_NAME: Not applicable — [one-line reason]
  §NUM PATTERN_NAME: FINDING (followed by the finding block below)

For each finding, include the full content using this template:

FINDING_FILE: {SEVERITY}-s{SECTION_NUM}-{kebab-description}.md
## [SEVERITY] Title
**Location**: `file:line`
**Description**: What the bug is and why it matters
**Vulnerable Code**: [snippet]
**Attack Scenario**: [numbered steps]
**Recommendation**: How to fix
**References**: [links to relevant advisories or building-secure-contracts]

You MUST report on ALL patterns in the reference file — do not skip any.
~~~

**Exit**: All scanning agents returned. Each reported on every pattern in their reference file.

### Phase 3: Write Findings

After all scanning agents return, write finding files to the output directory (default `.bughunt_cosmos/`):

1. Parse each agent's response for `FINDING_FILE:` blocks
2. For each finding, Write the content to `{OUTPUT_DIR}/{filename}` using the filename from `FINDING_FILE:`
3. Create the output directory first if it doesn't exist

### Phase 4: Verify Completeness

After writing all findings, verify every pattern was assessed:

1. Collect the summary lines (§NUM entries) returned by each agent
2. Check pattern counts against expected totals:
   - `core-scanner`: 8 patterns (§1-9, excluding §8 legacy-only)
   - `state-scanner`: 13 patterns (§11-23)
   - `advanced-scanner`: 4 patterns (§24-27)
   - `evm-scanner` (if spawned): 10 patterns (§1-10)
   - `ibc-scanner` (if spawned): 16 patterns (§1-16)
   - `cosmwasm-scanner` (if spawned): 3 patterns (§1-3)
3. If any pattern is missing from a summary, flag it and re-prompt that agent
4. List all finding files written to the output directory with a `Glob` for `*.md`

**Exit**: All patterns accounted for. Finding files listed for the user.

---

## Success Criteria

- [ ] Discovery CLAUDE.md written with complete technical inventory and threat model
- [ ] All scanning agents completed and reported on every pattern in their reference file
- [ ] Pattern counts verified against expected totals (no patterns skipped)
- [ ] All findings written to output directory as individual markdown files
- [ ] Each finding file includes: severity, location, vulnerable code, attack scenario, recommendation

---

## Resources

- **Discovery & CLAUDE.md**: [DISCOVERY.md](resources/DISCOVERY.md)
- **Core patterns (§1-9)**: [VULNERABILITY_PATTERNS.md](resources/VULNERABILITY_PATTERNS.md)
- **State & module patterns (§11-23)**: [STATE_VULNERABILITY_PATTERNS.md](resources/STATE_VULNERABILITY_PATTERNS.md)
- **Advanced patterns (§24-27)**: [ADVANCED_VULNERABILITY_PATTERNS.md](resources/ADVANCED_VULNERABILITY_PATTERNS.md)
- **IBC vulnerabilities**: [IBC_VULNERABILITY_PATTERNS.md](resources/IBC_VULNERABILITY_PATTERNS.md)
- **CosmWasm vulnerabilities**: [COSMWASM_VULNERABILITY_PATTERNS.md](resources/COSMWASM_VULNERABILITY_PATTERNS.md)
- **EVM vulnerabilities**: [EVM_VULNERABILITY_PATTERNS.md](resources/EVM_VULNERABILITY_PATTERNS.md)
- **Building Secure Contracts**: `building-secure-contracts/not-so-smart-contracts/cosmos/`
- **Cosmos SDK Docs**: https://docs.cosmos.network/
- **CodeQL for Cosmos SDK**: https://github.com/crypto-com/cosmos-sdk-codeql
