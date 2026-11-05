# Spec Parsing Patterns Reference

Extraction rules for turning protocol specifications into sequence diagram
content. Covers four spec formats. Read the section matching your input.

---

## RFC Format

RFCs follow a predictable structure. Use it to locate the right content fast.

### Locating the protocol description

1. **Find the handshake section**: search for "handshake", "key exchange",
   "authentication", "message flow", or "overview" in section titles
2. **Find message definitions**: sections titled "Messages", "Record Layer",
   "Handshake Protocol", or numbered `X.Y` subsections for each message type
3. **Find ASCII diagrams**: many RFCs embed sequence diagrams in code blocks
   using `->` or `<-` arrows — use these as a starting point for message
   ordering. If an ASCII diagram and the normative prose conflict, the prose
   takes precedence — RFC ASCII diagrams are illustrative, not normative.

### Extracting parties

- Parties are usually named in the introduction or in a "Notation" / "Overview"
  section: look for "client", "server", "initiator", "responder"
- Role names in RFCs are typically lowercase (`client`, `server`) — capitalise
  them in the diagram

### Extracting message flow

Arrow patterns in RFC prose and ASCII diagrams:

```
Client                                           Server
  |                                                |
  |----------ClientHello------------------------->|
  |<---------ServerHello + {EncryptedExtensions}--|
```

Also watch for:
- "The client sends a X message containing ..."
- "Upon receiving X, the server MUST ..."
- "The handshake proceeds as follows:" followed by a numbered list

`MUST`/`SHALL` clauses describe required steps; `MAY`/`SHOULD` describe
optional ones (use `opt` blocks in the diagram).

### Extracting crypto operations

RFCs typically define crypto in a "Cryptographic Computations" or "Key
Schedule" section. Look for:
- `HKDF-Extract`, `HKDF-Expand`, `Derive-Secret` — key derivation
- `Sign(sk, transcript)`, `Verify(pk, transcript, sig)` — signatures
- Encryption notation: `{...}` braces around a message mean it is encrypted
  (TLS convention); note which key is used in the surrounding prose
- Transcript hash: running hash over all handshake messages — annotate as
  `H(handshake_transcript)` at the point it is finalised

### ABNF grammars

ABNF defines message structure, not flow. Use it to populate arrow labels:

```
ClientHello = ProtocolVersion random [SessionID] CipherSuites Extensions
```

→ Arrow label: `ClientHello(version, random, session_id, cipher_suites, extensions)`

---

## Academic Paper / Pseudocode

Papers vary widely, but protocol descriptions follow common conventions.

### Locating the protocol description

- Look for boxes or figures labelled "Protocol X", "Figure X: Protocol name",
  "Algorithm X"
- Section titles: "Protocol Description", "Construction", "Our Protocol",
  "The Scheme", "Formal Description"
- Some papers give an informal description first, then a formal pseudocode box —
  prefer the pseudocode box for message flow accuracy

### Extracting parties

- Header row of a protocol figure: `Alice | Bob`, `Client | Server`, `P | V`
- Pseudocode function names: `Client.KeyGen()`, `Server.Respond()`,
  `Prover.Commit()`, `Verifier.Challenge()`
- Subscripts in mathematical notation: `pk_A`, `sk_B` — `A` and `B` are parties

### Extracting message flow

**Two-column layouts** (most common):

```
Alice                    Bob
---                      ---
Compute x ← f(...)
Send x ──────────────►
                         Receive x
                         Compute y ← g(x, ...)
         ◄────────────── Send y
Receive y
```

Read left-to-right for Alice's column, right-to-left for Bob's. Arrows cross
the column boundary to indicate message sends.

**Numbered step lists**:

```
1. A generates (pk, sk) ← KeyGen(1^λ)
2. A sends pk to B
3. B computes c ← Enc(pk, m) and sends c to A
4. A decrypts m' ← Dec(sk, c)
```

Map step numbers to rounds. A step that says "X sends Y to Z" is a message
arrow. A step that says "X computes ..." is a `Note over X` annotation.

**Pseudocode with explicit send/receive**:

```
function Round1_Alice(sk_A, pk_B):
    ek, epk = DH.KeyGen()
    msg = epk
    send(Bob, msg)
    return ek

function Round1_Bob(pk_A):
    epk_A = recv(Alice)
    ...
```

Treat `send(Party, msg)` as a message arrow, `recv(Party)` as the receiving
end of the previous arrow.

### Mathematical notation quick-reference

| Notation | Meaning |
|----------|---------|
| `←` or `:=` | assignment / output of a computation |
| `←$` or `←_R` | sample uniformly at random |
| `→` or `\leftarrow` between parties | message send |
| `\{m\}_k` or `Enc_k(m)` | encryption of `m` under key `k` |
| `[m]_sk` or `Sign_{sk}(m)` | signature on `m` with key `sk` |
| `H(m)` | hash |
| `\pi` or `Π` | protocol |
| `\lambda` | security parameter |
| `\bot` | reject / abort |

---

## Informal Prose

Informal descriptions vary the most. Apply these heuristics systematically.

### Locating the description

- Section headings: "Protocol Overview", "How It Works", "Flow", "Steps"
- Numbered or bulleted lists of protocol steps
- Diagrams embedded as images (describe what you can infer; note you cannot
  read image content)

### Extracting parties

- Look for the first paragraph that names the participants: "Alice and Bob",
  "the client and the server", "the initiator and responder"
- Use the first two prominent nouns that interact: if the text says "the user
  authenticates to the service", parties are `User` and `Service`

### Extracting message flow — sentence patterns

Arrow syntax in the table below maps to Mermaid (`->>` solid, `-->>` dashed).

| Pattern | Arrow |
|---------|-------|
| "A sends [msg] to B" | `A->>B: msg` |
| "B receives [msg] from A" | `A->>B: msg` (same arrow, B's perspective) |
| "A transmits / delivers / forwards [msg]" | `A->>B: msg` (infer B from context) |
| "B responds with [msg]" | `B-->>A: msg` |
| "A and B exchange [msg]" | use two arrows if asymmetric, or `Note over A,B` if symmetric |
| "A computes / derives / generates [value]" | `Note over A: compute value` |
| "if [condition] then [action]" | `alt condition` block |
| "optionally, A sends [msg]" | `opt description` block |

### Handling vague crypto

If the prose says "encrypts" without specifying the scheme:
- Use `Enc(k, plaintext) → ct` in the note
- Add `⚠️ encryption scheme not specified in spec`

If the prose says "signs" without specifying the algorithm:
- Use `Sign(sk, msg) → σ`
- Add `⚠️ signature algorithm not specified`

---

## Formal Verification Models

### ProVerif (`.pv`)

ProVerif models processes, not a narrative sequence. Map process structure to
sequence diagram steps.

**Key constructs:**

```proverif
(* Channel declaration *)
free c: channel.                    (* public channel *)
free s: channel [private].          (* private / secure channel *)

(* Free names — constants known to attacker if not private *)
free pk_A: bitstring.

(* Process definition *)
let ClientProc(sk: bitstring, pk_S: bitstring) =
    new nonce: bitstring;           (* fresh random — Note over Client: nonce ← rand *)
    out(c, nonce);                  (* send on channel c → arrow to Server *)
    in(c, resp: bitstring);         (* receive on channel c → arrow from Server *)
    let (m1, sig) = resp in
    if verify(m1, sig, pk_S) then  (* conditional — alt block *)
        ...
    else 0.                         (* abort path *)

(* Main process — composition of roles *)
process
    ( !ClientProc(sk_A, pk_S) | !ServerProc(sk_S, pk_A) )
```

**Extraction rules:**

| Construct | Diagram element |
|-----------|----------------|
| `let ProcName(params) =` | Defines a role; `ProcName` → participant |
| `new x: t` | `Note over Party: x ← fresh()` |
| `out(ch, msg)` | Arrow from this process to the process that `in`s on same `ch` |
| `in(ch, x)` | Receiving end of the matching `out` |
| `if cond then P else Q` | `alt cond` / `else` block |
| `let (a, b) = msg` | Destructuring — local computation, `Note over Party` |
| `!P` | Replication — this role handles multiple sessions; use `loop` annotation |
| `senc(m, k)` / `sdec(c, k)` | Symmetric enc/dec |
| `aenc(m, pk)` / `adec(c, sk)` | Asymmetric enc/dec |
| `sign(m, sk)` / `verify(m, sig, pk)` | Sign / verify |
| `hash(m)` | Hash |
| `pk(sk)` | Public key derivation — `Note over Party: pk = pk(sk)` |

**Channel matching:** Pair each `out(ch, msg)` with the `in(ch, x)` in another
process on the same channel. The sending process owns the arrow's tail; the
receiving process owns the arrow's head.

**Private channels** (`[private]` or declared with `new c`): represent
out-of-band communication — annotate: `Note over A,B: via private channel`.

**`phase N` construct:** ProVerif's `phase N` keyword sequences protocol steps
that cannot execute concurrently. Steps in phase N execute only after all phase
N-1 processes have terminated. If a model uses `phase`, use the phase numbers
to order the diagram: steps in phase 0 come before steps in phase 1, and so on.
Annotate phase boundaries: `Note over A,B: --- phase N begins ---`.

**Queries** (`query attacker(x)`, `query event(...)`) are security properties,
not protocol steps — omit from the diagram but mention in the Protocol Summary.

### Tamarin (`.spthy`)

**Important — Dolev-Yao attacker model:** Tamarin does not model direct
peer-to-peer channels. Every `Out(m)` delivers to the attacker network, and
every `In(m)` can be satisfied by any message the attacker knows (including
forwarded or replayed messages). For the diagram, treat `Out(m)` in one rule
and `In(m)` in another as a logical A→B message, but always add this note on
the diagram:

```
Note over A,B: ⚠️ Tamarin uses Dolev-Yao model — all messages transit adversary network
```

Tamarin models rules that fire when their premises are satisfied. Map rule
ordering to protocol steps.

**Key constructs:**

```tamarin
rule Register_pk:
    [ Fr(~sk) ]                     (* fresh secret key generated *)
  --[ Register($A, pk(~sk)) ]->    (* security annotation — not a message *)
    [ !Ltk($A, ~sk)                 (* persistent fact — stored state *)
    , !Pk($A, pk(~sk))              (* persistent fact — public key *)
    , Out(pk(~sk)) ]                (* send public key to network *)

rule Client_Send:
    [ Fr(~n)                        (* fresh nonce *)
    , !Pk($S, pk_S) ]               (* lookup server's public key *)
  --[ Send($C, $S, ~n) ]->
    [ St_Client_1($C, $S, ~n)       (* client state after round 1 *)
    , Out(aenc(~n, pk_S)) ]         (* send encrypted nonce *)

rule Server_Recv:
    [ In(aenc(n, pk(~sk)))          (* receive encrypted nonce *)
    , !Ltk($S, ~sk) ]               (* lookup server's secret key *)
  --[ Recv($S, n) ]->
    [ Out(n) ]                      (* echo decrypted nonce *)
```

**Extraction rules:**

| Construct | Diagram element |
|-----------|----------------|
| `Fr(~x)` in premise | `Note over Party: x ← fresh()` |
| `In(m)` in premise | Receive arrow — find matching `Out(m)` rule for sender |
| `Out(m)` in conclusion | Send arrow to network / other party |
| `!Fact($A, ...)` | Persistent state lookup — not a message |
| `St_Role_N(...)` | State fact — marks which round the party is in |
| `--[ Label ]->` | Security event annotation — omit from diagram |
| `$A` (public name) | Party / principal |
| `~x` (fresh name) | Freshly generated secret |
| `#i` (timepoint) | Ordering hint — earlier timepoint = earlier in diagram |

**Rule ordering:** Reconstruct order by following state facts: `St_Role_N`
consumed by a rule → `St_Role_{N+1}` produced → next rule for that role.
