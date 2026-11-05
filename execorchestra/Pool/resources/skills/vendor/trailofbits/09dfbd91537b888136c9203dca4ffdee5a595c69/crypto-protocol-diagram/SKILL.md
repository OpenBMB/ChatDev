---
name: crypto-protocol-diagram
description: "Extracts protocol message flow from source code, RFCs, academic papers, pseudocode, informal prose, ProVerif (.pv), or Tamarin (.spthy) models and generates Mermaid sequenceDiagrams with cryptographic annotations. Use when diagramming a crypto protocol, visualizing a handshake or key exchange flow, extracting message flow from a spec or RFC, diagramming a ProVerif or Tamarin model, or drawing sequence diagrams for TLS, Noise, Signal, X3DH, Double Ratchet, FROST, DH, or ECDH protocols."
---

# Crypto Protocol Diagram

Produces a Mermaid `sequenceDiagram` (written to file) and an ASCII sequence
diagram (printed inline) from either:

- **Source code** implementing a cryptographic protocol, or
- **A specification** — RFC, academic paper, pseudocode, informal prose,
  ProVerif (`.pv`), or Tamarin (`.spthy`) model.

**Tools used:** Read, Write, Grep, Glob, Bash, WebFetch (for URL specs).

Unlike the `diagramming-code` skill (which visualizes code structure), this skill
extracts **protocol semantics**: who sends what to whom, what cryptographic
transformations occur at each step, and what protocol phases exist.

For call graphs, class hierarchies, or module dependency maps, use the
`diagramming-code` skill instead.

## When to Use

- User asks to diagram, visualize, or extract a cryptographic protocol
- Input is source code implementing a handshake, key exchange, or multi-party protocol
- Input is an RFC, academic paper, pseudocode, or formal model (ProVerif/Tamarin)
- User names a specific protocol (TLS, Noise, Signal, X3DH, FROST)

## When NOT to Use

- User wants a call graph, class hierarchy, or module dependency map — use `diagramming-code`
- User wants to formally verify a protocol — use `mermaid-to-proverif` (after generating the diagram)
- Input has no cryptographic protocol semantics (no parties, no message exchange)

## Rationalizations to Reject

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The protocol is simple, I can diagram from memory" | Memory-based diagrams miss steps and invert arrows | Read the source or spec systematically |
| "I'll skip the spec path since code exists" | Code may diverge from the spec — both paths catch different bugs | When both exist, run spec workflow first, then annotate code divergences |
| "Crypto annotations are optional decoration" | Without crypto annotations, the diagram is just a message flow — useless for security review | Annotate every cryptographic operation |
| "The abort path is obvious, no need for alt blocks" | Implicit abort handling hides missing error checks | Show every abort/error path with `alt` blocks |
| "I don't need to check the examples first" | The examples define the expected output quality bar | Study the relevant example before working on unfamiliar input |
| "ProVerif/Tamarin models are code, not specs" | Formal models are specifications — they describe intended behavior, not implementation | Use the spec workflow (S1–S5) for `.pv` and `.spthy` files |

---

## Workflow

```
Protocol Diagram Progress:
- [ ] Step 0: Determine input type (code / spec / both)
- [ ] Step 1 (code) or S1–S5 (spec): Extract protocol structure
- [ ] Step 6: Generate sequenceDiagram
- [ ] Step 7: Verify and deliver
```

---

### Step 0: Determine Input Type

Before doing anything else, classify the input:

| Signal | Input type |
|--------|-----------|
| Source file extensions (`.py`, `.rs`, `.go`, `.ts`, `.js`, `.cpp`, `.c`) | **Code** |
| Function/class definitions, import statements | **Code** |
| RFC-style section headers (`§`, `Section X.Y`, `MUST`/`SHALL` keywords) | **Spec** |
| `Algorithm`/`Protocol`/`Figure` labels, mathematical notation | **Spec** |
| ProVerif file (`.pv`) with `process`, `let`, `in`/`out` | **Spec** |
| Tamarin file (`.spthy`) with `rule`, `--[...]->` | **Spec** |
| Plain prose or numbered steps describing a protocol | **Spec** |
| Both source files and a spec document | **Both** (annotate divergences with `⚠️`) |

- **Code only** → skip to Step 1 below
- **Spec only** → skip to Spec Workflow (S1–S5) below
- **Both** → run Spec Workflow first, then use the code-reading steps to verify
  the implementation against the spec diagram and annotate any divergences with `⚠️`
- **Ambiguous** → ask the user: "Is this a source code file, a specification
  document, or both?"

---

### Step 1: Locate Protocol Entry Points

Grep for function names, type names, and comments that reveal the protocol:

```bash
# Find handshake, session, round, phase entry points
rg -l "handshake|session_init|round[_0-9]|setup|keygen|send_msg|recv_msg" {targetDir}

# Find crypto primitives in use
rg "sign|verify|encrypt|decrypt|dh|ecdh|kdf|hkdf|hmac|hash|commit|reveal|share" \
    {targetDir} --type-add 'src:*.{py,rs,go,ts,js,cpp,c}' -t src -l
```

Start reading from the highest-level orchestration function — the one that calls
into handshake phases or the main protocol loop.

### Step 2: Identify Parties and Roles

Extract participant names from:

- Struct/class names: `Client`, `Server`, `Initiator`, `Responder`, `Prover`,
  `Verifier`, `Dealer`, `Party`, `Coordinator`
- Function parameter names that carry state for a role
- Comments declaring the protocol role
- Test fixtures that set up two-party or N-party scenarios

Map these to Mermaid `participant` declarations. Use short, readable aliases:

```
participant I as Initiator
participant R as Responder
```

### Step 3: Trace Message Flow

Follow state transitions and network sends/receives. Look for patterns like:

| Pattern | Meaning |
|---------|---------|
| `send(msg)` / `recv()` | Direct message exchange |
| `serialize` + `transmit` | Structured message sent |
| Return value passed to other party's function | Logical message (in-process) |
| `round1_output` → `round2_input` | Round-based MPC step |
| Struct fields named `ephemeral_key`, `ciphertext`, `mac`, `tag` | Message contents |

For **in-process** protocol implementations (where both parties run in the same
process), treat function call boundaries as logical message sends when they
represent what would be a network boundary in deployment.

### Step 4: Annotate Cryptographic Operations

At each protocol step, identify and label:

| Operation | Diagram annotation |
|-----------|-------------------|
| Key generation | `Note over A: keygen(params) → pk, sk` |
| DH / ECDH | `Note over A,B: DH(sk_A, pk_B)` |
| KDF / HKDF | `Note over A: HKDF(ikm, salt, info)` |
| Signing | `Note over A: Sign(sk, msg) → σ` |
| Verification | `Note over B: Verify(pk, msg, σ)` |
| Encryption | `Note over A: Enc(key, plaintext) → ct` |
| Decryption | `Note over B: Dec(key, ct) → plaintext` |
| Commitment | `Note over A: Commit(value, rand) → C` |
| Hash | `Note over A: H(data) → digest` |
| Secret sharing | `Note over D: Share(secret, t, n) → {s_i}` |
| Threshold combine | `Note over C: Combine({s_i}) → secret` |

Keep annotations concise — use mathematical shorthand, not code.

### Step 5: Identify Protocol Phases

Group message steps into named phases using `rect` or `Note` blocks:

Common phases to detect:
- **Setup / Key Generation**: party key creation, trusted setup, parameter gen
- **Handshake / Init**: ephemeral key exchange, nonce exchange, version negotiation
- **Authentication**: identity proof, certificate exchange, signature verification
- **Key Derivation**: session key derivation from shared secrets
- **Data Transfer / Main Protocol**: encrypted application data exchange
- **Finalization / Teardown**: session close, MAC verification, abort handling

Detect abort/error paths and show them with `alt` blocks.

---

## Spec Workflow (S1–S5)

Use this path when the input is a specification document rather than source code.
After completing S1–S5, continue with Step 6 (Generate sequenceDiagram) and
Step 7 (Verify and deliver) from the code workflow above.

### Step S1: Ingest the Spec

Obtain the full spec text:

- **File path provided** → read with the Read tool
- **URL provided** → fetch with WebFetch
- **Pasted inline** → work directly from conversation context

Then identify the spec format and read
[references/spec-parsing-patterns.md](references/spec-parsing-patterns.md)
for format-specific extraction guidance:

| Format | Signals |
|--------|---------|
| RFC | `RFC XXXX`, `MUST`/`SHALL`/`SHOULD`, ABNF grammars, section-numbered prose |
| Academic paper / pseudocode | `Algorithm X`, `Protocol X`, `Figure X`, numbered steps, `←`/`→` in math mode |
| Informal prose | Numbered lists, "A sends B ...", plain English descriptions |
| ProVerif (`.pv`) | `process`, `let`, `in(ch, x)`, `out(ch, msg)`, `!` (replication) |
| Tamarin (`.spthy`) | `rule`, `--[ ]->`, `Fr(~x)`, `!Pk(A, pk)`, `In(m)`, `Out(m)` |

If the spec references a known named protocol (TLS, Noise, Signal, X3DH, Double
Ratchet, FROST), also read
[references/protocol-patterns.md](references/protocol-patterns.md) to use its
canonical flow as a skeleton and fill in spec-specific details.

### Step S2: Extract Parties and Roles

Identify all protocol participants. Look for:

- **Named roles** in prose or pseudocode: `Alice`, `Bob`, `Client`, `Server`,
  `Initiator`, `Responder`, `Prover`, `Verifier`, `Dealer`, `Party_i`,
  `Coordinator`, `Signer`
- **Section headers**: "Parties", "Roles", "Participants", "Setup", "Notation"
- **ProVerif**: process names at top level (`let ClientProc(...)`, `let ServerProc(...)`)
- **Tamarin**: rule names and fact arguments (e.g. `!Pk($A, pk)` — `$A` is a party)

Map each role to a Mermaid `participant` declaration. Use short IDs with
descriptive aliases (see naming conventions in
[references/mermaid-sequence-syntax.md](references/mermaid-sequence-syntax.md)).

### Step S3: Extract Message Flow

Trace what each party sends to whom and in what order. Extraction patterns by format:

**RFC / informal prose:**
- Arrow notation: `A → B: msg`, `A -> B`
- Sentence patterns: "A sends B ...", "B responds with ...", "A transmits ...",
  "upon receiving X, B sends Y"
- Numbered steps: extract in order, inferring sender/receiver from context

**Pseudocode:**
- Function signatures with explicit `sender`/`receiver` parameters
- `send(party, msg)` / `receive(party)` calls
- Return values passed as inputs to the other party's function in the next step

**ProVerif (`.pv`):**
- `out(ch, msg)` — send on channel `ch`
- `in(ch, x)` — receive on channel `ch`, bind to `x`
- Match `out`/`in` pairs on the same channel to identify message flows
- `!` (replication) signals a role that handles multiple sessions

**Tamarin (`.spthy`):**
- `In(m)` premise — receive message `m`
- `Out(m)` conclusion — send message `m`
- Rule name and ordering of rules reveal protocol rounds
- `Fr(~x)` — fresh random value generated by a party
- `--[ Label ]->` facts — security annotations, not messages

Preserve the ordering and round structure. Group concurrent sends (broadcast)
using `par` blocks in the final diagram.

### Step S4: Extract Cryptographic Operations

For each protocol step, identify the cryptographic operations performed and which
party performs them:

| Spec notation | Operation | Diagram annotation |
|---------------|-----------|-------------------|
| `keygen()`, `Gen(1^λ)` | Key generation | `Note over A: keygen() → pk, sk` |
| `DH(a, B)`, `g^ab` | DH / ECDH | `Note over A,B: DH(sk_A, pk_B)` |
| `KDF(ikm)`, `HKDF(...)` | Key derivation | `Note over A: HKDF(ikm, salt, info) → k` |
| `Sign(sk, m)`, `σ ← Sign` | Signing | `Note over A: Sign(sk, msg) → σ` |
| `Verify(pk, m, σ)` | Verification | `Note over B: Verify(pk, msg, σ)` |
| `Enc(k, m)`, `{m}_k` | Encryption | `Note over A: Enc(k, plaintext) → ct` |
| `Dec(k, c)` | Decryption | `Note over B: Dec(k, ct) → plaintext` |
| `H(m)`, `hash(m)` | Hash | `Note over A: H(data) → digest` |
| `Commit(v, r)`, `com` | Commitment | `Note over A: Commit(value, rand) → C` |
| ProVerif `senc(m, k)` | Symmetric encryption | `Note over A: Enc(k, m) → ct` |
| ProVerif `pk(sk)` | Public key derivation | `Note over A: pk = pk(sk)` |
| ProVerif `sign(m, sk)` | Signing | `Note over A: Sign(sk, m) → σ` |

Identify security conditions and abort paths:

- Prose: "if verification fails, abort", "only if ...", "reject if ..."
- Pseudocode: `assert`, `require`, `if ... abort`
- ProVerif: `if m = expected then ... else 0`
- Tamarin: contradicting facts or restriction lemmas

These become `alt` blocks in the final diagram.

### Step S5: Flag Spec Ambiguities

Before moving to Step 6, check for gaps:

- **Unclear message ordering**: infer from round structure or section order;
  annotate with `⚠️ ordering inferred from spec structure`
- **Implied parties**: if a party's role is implied but unnamed, give it a
  descriptive name and note the inference
- **Missing steps**: if the spec omits a step that the canonical pattern for
  this protocol requires, annotate:
  `⚠️ spec omits [step] — canonical protocol requires it`
- **Underspecified crypto**: if the spec says "encrypt" without specifying
  the scheme, annotate: `⚠️ encryption scheme not specified`
- **ProVerif/Tamarin**: private channels (`c` declared with `new c` or as a
  private free name) represent out-of-band channels — note them

---

<!-- Both code path (Steps 1–5) and spec path (Steps S1–S5) continue here -->

### Step 6: Generate sequenceDiagram

Produce Mermaid syntax following the rules in
[references/mermaid-sequence-syntax.md](references/mermaid-sequence-syntax.md).

**Completeness over brevity.** Show every distinct message type. Omit repeated
loop iterations (use `loop` blocks instead), but never omit a distinct protocol
step.

**Correctness over aesthetics.** The diagram must match what the code actually
does. If the code diverges from a known spec, annotate the divergence:

```
Note over A,B: ⚠️ spec requires MAC here — implementation omits it
```

### Step 7: Verify and Deliver

Before delivering:

- [ ] Every participant declared actually sends or receives at least one message
- [ ] Arrows point in the correct direction (sender → receiver)
- [ ] Cryptographic operations are on the correct party (the one computing them)
- [ ] If protocol phases are used, no arrows appear outside a phase block
- [ ] `alt` blocks cover known abort/error paths
- [ ] Diagram renders without syntax errors (check
      [references/mermaid-sequence-syntax.md](references/mermaid-sequence-syntax.md)
      for common pitfalls)
- [ ] If spec divergence found, annotated with `⚠️`

**Write the diagram to a file.** Choose a filename derived from the protocol
name, e.g. `noise-xx-handshake.md` or `x3dh-key-agreement.md`. Write a
Markdown file with this structure:

```markdown
# <Protocol Name> Sequence Diagram

\`\`\`mermaid
sequenceDiagram
    ...
\`\`\`

## Protocol Summary

- **Parties:** ...
- **Round complexity:** ...
- **Key primitives:** ...
- **Authentication:** ...
- **Forward secrecy:** ...
- **Notable:** [spec deviations or security observations, or "none"]
```

After writing the file, print an **ASCII sequence diagram** inline in the
response, followed by the Protocol Summary. State the output filename so the
user knows where to find the Mermaid source.

Follow all drawing conventions in
[references/ascii-sequence-diagram.md](references/ascii-sequence-diagram.md),
including the inline output format.

---

## Decision Tree

```
── Input is a spec document (not code)?
│  └─ Step S1: identify format, read references/spec-parsing-patterns.md
│
── Input is source code (not a spec)?
│  └─ Step 1: grep for handshake/round/send/recv entry points
│
── Both spec and code provided?
│  └─ Run Spec Workflow (S1–S5) first to build canonical diagram,
│     then read code and annotate divergences with ⚠️
│
── Spec is a known protocol (TLS, Noise, Signal, X3DH, FROST)?
│  └─ Read references/protocol-patterns.md and use canonical flow as skeleton
│
── Spec is ProVerif (.pv) or Tamarin (.spthy)?
│  └─ Read references/spec-parsing-patterns.md → Formal Models section
│
── Spec message ordering is ambiguous?
│  └─ Infer from round/section structure, annotate with ⚠️
│
── Can't identify parties from spec?
│  └─ Check "Parties"/"Notation" sections; for ProVerif read process names;
│     for Tamarin read rule names and fact arguments
│
── Don't know which code files implement the protocol?
│  └─ Step 1: grep for handshake/round/send/recv entry points
│
── Can't identify parties from struct names?
│  └─ Read test files — test setup reveals roles
│
── Protocol runs in-process (no network calls)?
│  └─ Treat function argument passing at role boundaries as messages
│
── MPC / threshold protocol with N parties?
│  └─ Read references/protocol-patterns.md → MPC section
│
── Mermaid syntax error?
│  └─ Read references/mermaid-sequence-syntax.md → Common Pitfalls
│
└─ ASCII drawing conventions?
   └─ Read references/ascii-sequence-diagram.md
```

---

## Examples

**Code path** — `examples/simple-handshake/`:

- **`protocol.py`** — two-party authenticated key exchange (X25519 DH +
  Ed25519 signing + HKDF + ChaCha20-Poly1305)
- **`expected-output.md`** — exact ASCII diagram and Mermaid file the skill
  should produce for that protocol

**Spec path (ProVerif)** — `examples/simple-proverif/`:

- **`model.pv`** — HMAC challenge-response authentication modeled in ProVerif
- **`expected-output.md`** — step-by-step extraction walkthrough (parties,
  message flow, crypto ops) and the exact ASCII diagram and Mermaid file the
  skill should produce

Study the relevant example before working on an unfamiliar input.

---

## Supporting Documentation

- **[references/spec-parsing-patterns.md](references/spec-parsing-patterns.md)** —
  Extraction rules for RFC, academic paper/pseudocode, informal prose, ProVerif,
  and Tamarin input formats; read during Step S1
- **[references/mermaid-sequence-syntax.md](references/mermaid-sequence-syntax.md)** —
  Participant syntax, arrow types, activations, grouping blocks, escaping rules,
  and common rendering pitfalls
- **[references/protocol-patterns.md](references/protocol-patterns.md)** —
  Canonical message flows for TLS 1.3, Noise, X3DH, Double Ratchet, Shamir
  secret sharing, commit-reveal, and generic MPC rounds; use as a reference
  when comparing implementation against spec
- **[references/ascii-sequence-diagram.md](references/ascii-sequence-diagram.md)** —
  Column layout, arrow conventions, self-loops, phase labels, and inline
  output format for the ASCII diagram
