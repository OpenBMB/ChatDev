# Expected Skill Output

This file shows what the `crypto-protocol-diagram` skill should produce when
run on `protocol.py`. It covers both the inline response (ASCII diagram +
Protocol Summary) and the written Mermaid file.

---

## Inline Response

```
Protocol: Simple Authenticated Key Exchange
Output:   simple-authenticated-key-exchange.md

Initiator                          Responder
   |                                   |
   |   -- Setup (out-of-band) --       |
   +--.                                |
   |  | keygen() → sk_i, pk_i          |
   |<-'                                |
   |                                   +--.
   |                    keygen() → sk_r, pk_r |
   |                                   |<-'
   |                                   |
   |   -- Handshake --                 |
   +--.                                |
   |  | keygen() → ek_i, epk_i         |
   |  | sig_i = Sign(sk_i, "msg1"||epk_i) |
   |<-'                                |
   |                                   |
   +---------------------------------->|  epk_i || sig_i
   |                                   |
   |                                   +--.
   |           Verify(pk_i, sig_i)     |  |
   |     keygen() → ek_r, epk_r        |  |
   |  sig_r = Sign(sk_r, "msg2"||transcript) |
   |     dh = DH(ek_r, epk_i)          |  |
   |     sk = HKDF(dh, transcript)     |<-'
   |                                   |
   |<- - - - - - - - - - - - - - - - - +  epk_r || sig_r
   |                                   |
   +--.                                |
   |  | Verify(pk_r, sig_r)            |
   |  | dh = DH(ek_i, epk_r)           |
   |  | sk = HKDF(dh, transcript)      |
   |<-'                                |
   |                                   |
   |   -- Application Data --          |
   |                                   |
   +---------------------------------->|  ChaCha20Poly1305(sk, nonce, plaintext)
   |                                   |

   [on signature verification failure]
   |  abort(INVALID_SIGNATURE)         |
   |<- - - - - - - - - - - - - - - - - +

## Protocol Summary

- **Parties:** Initiator, Responder
- **Round complexity:** 1 round trip (2 messages)
- **Key primitives:** X25519 (ephemeral DH), Ed25519 (signing), HKDF-SHA256, ChaCha20-Poly1305
- **Authentication:** mutual — both parties sign their ephemeral keys with long-term Ed25519 keys
- **Forward secrecy:** yes — session key derived from ephemeral DH; compromise of static keys does not expose past sessions
- **Notable:** static keys are assumed registered out-of-band (no in-protocol key transmission); transcript binding covers only ephemeral public keys, not party identities — an implementation that doesn't bind pk_i and pk_r into the transcript is vulnerable to identity mislabeling
```

---

## Written Mermaid File (`simple-authenticated-key-exchange.md`)

```markdown
# Simple Authenticated Key Exchange Sequence Diagram

\`\`\`mermaid
sequenceDiagram
    participant I as Initiator
    participant R as Responder

    rect rgba(100, 149, 237, 0.15)
        Note over I,R: Setup (out-of-band key registration)
        Note over I: keygen() → sk_i, pk_i
        Note over R: keygen() → sk_r, pk_r
    end

    rect rgba(46, 204, 113, 0.15)
        Note over I,R: Handshake
        Note over I: keygen() → ek_i, epk_i
        Note over I: sig_i = Sign(sk_i, "msg1" || epk_i)
        I->>R: epk_i || sig_i
        Note over R: Verify(pk_i, "msg1" || epk_i, sig_i)
        Note over R: keygen() → ek_r, epk_r
        Note over R: transcript = epk_i || epk_r
        Note over R: sig_r = Sign(sk_r, "msg2" || transcript)
        Note over R: dh = DH(ek_r, epk_i)
        Note over R: sk_r = HKDF(dh || transcript, info="session-key-v1")
        R-->>I: epk_r || sig_r
        Note over I: Verify(pk_r, "msg2" || transcript, sig_r)
        Note over I: dh = DH(ek_i, epk_r)
        Note over I: sk_i = HKDF(dh || transcript, info="session-key-v1")
    end

    rect rgba(241, 196, 15, 0.15)
        Note over I,R: Application Data
        I->>R: ChaCha20Poly1305(sk, nonce, plaintext)
    end

    alt signature verification failure
        R-->>I: abort(INVALID_SIGNATURE)
    end
\`\`\`

## Protocol Summary

- **Parties:** Initiator, Responder
- **Round complexity:** 1 round trip (2 messages)
- **Key primitives:** X25519 (ephemeral DH), Ed25519 (signing), HKDF-SHA256, ChaCha20-Poly1305
- **Authentication:** mutual — both parties sign their ephemeral keys with long-term Ed25519 keys
- **Forward secrecy:** yes — session key derived from ephemeral DH; compromise of static keys does not expose past sessions
- **Notable:** static keys are assumed registered out-of-band (no in-protocol key transmission); transcript binding covers only ephemeral public keys, not party identities — an implementation that doesn't bind pk_i and pk_r into the transcript is vulnerable to identity mislabeling
```
