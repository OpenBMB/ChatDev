# Property-Based Testing Skill

A Claude Code skill that provides guidance for property-based testing (PBT) across multiple programming languages and smart contract development.

## What This Skill Does

When activated, this skill helps Claude:

- **Detect PBT opportunities** - Recognizes patterns like encode/decode pairs, validators, normalizers, pure functions, and smart contract invariants
- **Generate property-based tests** - Creates tests with appropriate strategies, properties, and edge cases
- **Review existing PBT tests** - Identifies issues like tautological properties, vacuous tests, and weak assertions
- **Design with properties** - Uses Property-Driven Development to define specifications before implementation
- **Refactor for testability** - Suggests code changes that enable stronger property testing

## Supported Languages

| Language | Library | Notes |
|----------|---------|-------|
| Python | Hypothesis | |
| JavaScript/TypeScript | fast-check | |
| Rust | proptest | Also: quickcheck |
| Go | rapid | Also: gopter |
| Java | jqwik | |
| Scala | ScalaCheck | |
| C# | FsCheck | |
| Elixir | StreamData | |
| Haskell | QuickCheck | Also: Hedgehog |
| Clojure | test.check | |
| Ruby | PropCheck | |
| Kotlin | Kotest | |
| Swift | SwiftCheck | Unmaintained |
| C++ | RapidCheck | |

### Smart Contract Testing

| Tool | Platform | Description |
|------|----------|-------------|
| Echidna | EVM/Solidity | Property-based fuzzer |
| Medusa | EVM/Solidity | Next-gen parallel fuzzer |

See [secure-contracts.com](https://secure-contracts.com) for tutorials.

## File Structure

```
property-based-testing/
├── SKILL.md           # Entry point - detection patterns and routing
├── README.md          # This file
└── references/
    ├── generating.md  # How to write property-based tests
    ├── reviewing.md   # How to evaluate test quality
    ├── strategies.md  # Input generation reference
    ├── design.md      # Property-Driven Development workflow
    ├── refactoring.md # Making code more testable
    └── libraries.md   # PBT library reference by language
```

## Usage

The skill activates automatically when Claude detects relevant patterns:

- Serialization pairs (`encode`/`decode`, `serialize`/`deserialize`)
- Validators and normalizers
- Pure functions with clear input/output types
- Data structure operations
- Smart contracts (Solidity/Vyper)

You can also invoke it explicitly by asking Claude to use property-based testing.

### Example Prompts

```
"Write property-based tests for this JSON serializer"
"Review this Hypothesis test for quality issues"
"Help me design this feature using properties first"
"This function is hard to test - how can I refactor it?"
"Write Echidna invariants for this token contract"
```

## Property Quick Reference

| Property | Pattern | Use Case |
|----------|---------|----------|
| Roundtrip | `decode(encode(x)) == x` | Serialization |
| Idempotence | `f(f(x)) == f(x)` | Normalization |
| Invariant | `property(f(x))` holds | Any transformation, smart contracts |
| Commutativity | `f(a,b) == f(b,a)` | Binary operations |
| Oracle | `new(x) == reference(x)` | Refactoring |
