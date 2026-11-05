# Constant-Time Analysis Skill

A Claude Code skill that detects timing side-channel vulnerabilities in cryptographic code by analyzing assembly or bytecode output for dangerous instructions.

## What This Skill Does

When activated, this skill helps Claude:

- **Detect timing vulnerabilities** - Identifies variable-time instructions (division, floating-point) that leak secrets through execution timing
- **Analyze across architectures** - Tests compiled output for x86_64, ARM64, RISC-V, and other targets
- **Support scripting languages** - Analyzes PHP, JavaScript/TypeScript, Python, and Ruby via bytecode
- **Guide constant-time fixes** - Provides patterns for Barrett reduction, constant-time selection, and safe comparisons
- **Integrate with CI** - Produces JSON output suitable for automated pipelines

## Supported Languages

| Language | Analysis Method | Reference Guide |
|----------|-----------------|-----------------|
| C/C++ | Assembly (gcc/clang) | [references/compiled.md](references/compiled.md) |
| Go | Assembly (go) | [references/compiled.md](references/compiled.md) |
| Rust | Assembly (rustc) | [references/compiled.md](references/compiled.md) |
| PHP | Zend opcodes (VLD/OPcache) | [references/php.md](references/php.md) |
| JavaScript | V8 bytecode (Node.js) | [references/javascript.md](references/javascript.md) |
| TypeScript | V8 bytecode (tsc + Node.js) | [references/javascript.md](references/javascript.md) |
| Python | CPython bytecode (dis) | [references/python.md](references/python.md) |
| Ruby | YARV bytecode | [references/ruby.md](references/ruby.md) |

## Supported Architectures (Compiled Languages)

| Architecture | Division Instructions | Common Use |
|--------------|----------------------|------------|
| x86_64 | DIV, IDIV | Servers, desktops |
| ARM64 | UDIV, SDIV | Mobile, Apple Silicon |
| ARM | UDIV, SDIV | Embedded |
| RISC-V | DIV, DIVU, REM | Emerging platforms |
| PowerPC | DIVW, DIVD | Legacy servers |
| s390x | D, DR, DL | Mainframes |
| i386 | DIV, IDIV | Legacy |

## File Structure

```text
skills/constant-time-analysis/
├── SKILL.md              # Entry point - routing and quick reference
├── README.md             # This file
└── references/
    ├── compiled.md       # C, C++, Go, Rust analysis
    ├── php.md            # PHP analysis (VLD installation, opcodes)
    ├── javascript.md     # JavaScript/TypeScript analysis
    ├── python.md         # Python analysis (dis module)
    └── ruby.md           # Ruby analysis (YARV)
```

The analyzer tool is located at `ct_analyzer/analyzer.py` in the plugin root.

## Usage

The skill activates automatically when Claude detects:

- Cryptographic code implementation (encryption, signing, key derivation)
- Questions about timing attacks or constant-time programming
- Code handling secret keys, tokens, or cryptographic material
- Functions with division/modulo operations on potentially secret data

You can also invoke it explicitly by asking Claude to check code for timing vulnerabilities.

### Example Prompts

```
"Check this crypto function for timing vulnerabilities"
"Is this signature verification constant-time?"
"Help me replace this division with Barrett reduction"
"Analyze this ML-KEM implementation for KyberSlash-style issues"
"What constant-time patterns should I use here?"
```

## Quick Reference

| Vulnerability | Detection | Fix |
|--------------|-----------|-----|
| Secret division | DIV, IDIV, SDIV, UDIV | Barrett reduction |
| Secret branches | JE, JNE, BEQ, BNE | Bit masking, cmov |
| Secret comparison | Early-exit memcmp | crypto/subtle |
| Variable-time FP | FDIV, FSQRT | Avoid in crypto |

## Real-World Attacks

- **KyberSlash (2023)** - Division in ML-KEM leaked keys
- **Lucky Thirteen (2013)** - Padding timing in TLS
- **Timing attacks on RSA** - Division in modular exponentiation
