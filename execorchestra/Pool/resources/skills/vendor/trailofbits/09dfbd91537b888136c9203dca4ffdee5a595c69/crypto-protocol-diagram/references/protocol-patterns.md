# Crypto Protocol Patterns Reference

Canonical message flows for common cryptographic protocols. Use these as a
reference when comparing an implementation against a known spec, or as a
starting skeleton when the implementation follows a named protocol.

---

## TLS 1.3 Handshake (RFC 8446)

**Parties:** Client (C), Server (S)
**Round complexity:** 1 RTT (0-RTT with resumption)

```
C → S: ClientHello(random, legacy_session_id, cipher_suites,
                   key_share[ecdhe], supported_versions=[TLS 1.3])

S → C: ServerHello(random, legacy_session_id, cipher_suite,
                   key_share[ecdhe], supported_versions=TLS 1.3)

Note: ECDHE shared secret derived by both sides
Note: HKDF chain: early_secret → handshake_secret → master_secret

S → C: {EncryptedExtensions}   (under handshake key)
S → C: {Certificate}           (server cert chain)
S → C: {CertificateVerify}     (Sign(sk_S, transcript))
S → C: {Finished}              (HMAC over transcript)

C → S: {Certificate}           (if mutual auth requested)
C → S: {CertificateVerify}     (Sign(sk_C, transcript))
C → S: {Finished}              (HMAC over transcript)

Both: derive application traffic keys from master_secret
C ↔ S: {Application Data}      (under application keys)
```

**Code signals:** Look for `ClientHello`, `ServerHello`, `key_share`,
`supported_versions`, `cipher_suite`, `HKDF`, `transcript_hash`, `Finished`.

---

## Noise Protocol Framework (https://noiseprotocol.org)

**Pattern family:** NN, NK, NX, KN, KK, KX, XN, XK, XX, IX, ...

### Noise_XX (most common: mutual auth, no prior knowledge)

**Parties:** Initiator (I), Responder (R)
**Round complexity:** 1.5 RTT

```
I → R: msg_1 = e
       (send ephemeral pubkey)

R → I: msg_2 = e, ee, s, es
       (send ephemeral pubkey,
        DH(e_R, e_I),
        send static pubkey encrypted,
        DH(s_R, e_I))

I → R: msg_3 = s, se
       (send static pubkey encrypted,
        DH(s_I, e_R))

Both: transport keys derived from chained hash state
I ↔ R: encrypted transport messages
```

**State machine:** `CipherState → SymmetricState → HandshakeState`.
Look for `MixKey`, `MixHash`, `EncryptAndHash`, `DecryptAndHash`,
`Split` (produces two `CipherState` objects for send/recv).

**Code signals:** `HandshakeState`, `CipherState`, `SymmetricState`,
`h` (handshake hash), `ck` (chaining key), `n` (nonce counter),
pattern strings like `"XX"`, `"IK"`.

### Noise_IK (identity-hiding initiator, known responder static key)

```
I → R: msg_1 = e, es, s, ss
       (ephemeral, DH(e_I, s_R), static (encrypted), DH(s_I, s_R))

R → I: msg_2 = e, ee, se
       (ephemeral, DH(e_R, e_I), DH(e_R, s_I))
```

---

## Signal Protocol

### X3DH (Extended Triple Diffie-Hellman) Key Agreement

**Parties:** Alice (A), Bob (B), Server (S)
**Purpose:** Establish shared secret for asynchronous messaging

```
Note over B: Publish to server:
             IK_B (identity key),
             SPK_B (signed prekey) + Sig(IK_B, SPK_B),
             {OPK_B_i} (one-time prekeys)

Note over A: Fetch Bob's key bundle from server
A → S: fetch_prekey_bundle(Bob)
S → A: IK_B, SPK_B, Sig, OPK_B_1

Note over A: Verify Sig(IK_B, SPK_B)
Note over A: EK_A = generate ephemeral keypair

Note over A: DH1 = DH(IK_A, SPK_B)
             DH2 = DH(EK_A, IK_B)
             DH3 = DH(EK_A, SPK_B)
             DH4 = DH(EK_A, OPK_B_1)  [if one-time prekey available]
             SK = KDF(DH1 || DH2 || DH3 || DH4)

A → B: InitialMessage(IK_A, EK_A, OPK_B_id, Enc(SK, initial_plaintext))

Note over B: Recompute DH1..DH4, derive SK
             Decrypt initial message
```

**Code signals:** `identity_key`, `signed_prekey`, `one_time_prekey`,
`ephemeral_key`, `X3DH`, `triple_dh`, `prekey_bundle`.

### Double Ratchet Algorithm

**Parties:** Alice, Bob (symmetric, both have SK from X3DH)
**Purpose:** Forward-secret, break-in-recovery message encryption

```
Note over A,B: Initialize with SK from X3DH
               A has B's ratchet public key

A → B: Header(dh_ratchet_pk_A, prev_chain_len, msg_num)
       || Enc(message_key, plaintext)
Note over B: DH ratchet step: new root_key, new chain_key
             Derive message_key from chain_key
             Decrypt

B → A: Header(dh_ratchet_pk_B, prev_chain_len, msg_num)
       || Enc(message_key, plaintext)
Note over A: DH ratchet step: new root_key, new chain_key
             Derive message_key from chain_key
             Decrypt
```

**Code signals:** `root_key`, `chain_key`, `message_key`, `ratchet_key`,
`sending_chain`, `receiving_chain`, `skip_message_keys`, `MessageKey`.

---

## Diffie-Hellman Key Exchange (Classic / ECDH)

**Parties:** Alice (A), Bob (B)
**Round complexity:** 1 RTT

```
Note over A: a = random scalar; g_a = g^a (or a·G for ECDH)
A → B: g_a

Note over B: b = random scalar; g_b = g^b (or b·G for ECDH)
B → A: g_b

Note over A: shared = g_b^a = g^(ab)
Note over B: shared = g_a^b = g^(ab)
Note over A,B: session_key = KDF(shared)
```

**Authenticated DH:** add signatures or MACs over the transcript to bind
identities. Without authentication, this is vulnerable to MITM.

---

## Challenge-Response Authentication

**Variants:** HMAC-based, signature-based, password-based (PAKE)

### Signature-based

```
C → S: authenticate_request(identity)
S → C: challenge(nonce, session_id)
Note over C: σ = Sign(sk_C, nonce || session_id || identity)
C → S: response(σ, pk_C)
Note over S: Verify(pk_C, nonce || session_id || identity, σ)

alt verification succeeds
    S → C: session_token
else verification fails
    S → C: auth_failure
end
```

**Code signals:** `challenge`, `nonce`, `sign`, `verify`, `response`,
`session_token`, `authenticate`.

### HMAC-based (shared secret)

```
C → S: auth_request(identity)
S → C: challenge(nonce)
Note over C: mac = HMAC(shared_key, nonce || identity)
C → S: response(mac)
Note over S: expected = HMAC(shared_key, nonce || identity)
             ct_equal(mac, expected)
```

---

## Shamir Secret Sharing

**Parties:** Dealer (D), Parties P1…Pn, Combiner (C)
**Setup:** (t, n) threshold

```
Note over D: Split secret s into n shares using degree-(t-1) polynomial
             f(x) = s + a_1·x + … + a_{t-1}·x^{t-1}
             share_i = f(i) for i = 1..n

D → P1: Enc(pk_1, share_1)
D → P2: Enc(pk_2, share_2)
...
D → Pn: Enc(pk_n, share_n)

# (t-of-n parties agree to reconstruct)

P1 → C: share_1
P2 → C: share_2
...
Pt → C: share_t

Note over C: Lagrange interpolation on {(i, share_i)}
             → recover f(0) = s
```

**Code signals:** `split`, `share`, `combine`, `threshold`, `lagrange`,
`polynomial`, `evaluate`.

---

## Commit-Reveal

**Parties:** Committer (C), Verifier (V)
**Purpose:** Bind to a value without revealing it; reveal later

```
rect rgba(100, 149, 237, 0.15)
    Note over C,V: Phase 1: Commit
    Note over C: r = random nonce
                 commitment = H(value || r)
    C → V: commitment
end

rect rgba(46, 204, 113, 0.15)
    Note over C,V: Phase 2: Reveal
    C → V: value, r
    Note over V: Check H(value || r) == commitment
end

alt commitment matches
    Note over V: value accepted
else mismatch
    Note over V: ABORT — equivocation detected
end
```

**Code signals:** `commit`, `reveal`, `commitment`, `open`, `binding`,
`hiding`.

---

## Generic N-Party MPC (Round-Based)

**Parties:** P1, P2, …, Pn
**Structure:** Preprocessing + Online phases, or direct rounds

```
rect rgba(100, 149, 237, 0.15)
    Note over P1,P3: Round 0: Input Commitment
    Note over P1: share_1_j = Share(input_1, t, n) for j=1..n
    P1 ->> P2: share_1_2
    P1 ->> P3: share_1_3
    Note over P2: share_2_j = Share(input_2, t, n)
    P2 ->> P1: share_2_1
    P2 ->> P3: share_2_3
    Note over P3: share_3_j = Share(input_3, t, n)
    P3 ->> P1: share_3_1
    P3 ->> P2: share_3_2
end

rect rgba(46, 204, 113, 0.15)
    Note over P1,P3: Round 1: Local Computation
    Note over P1: result_share_1 = f(share_1_1, share_2_1, share_3_1)
    Note over P2: result_share_2 = f(share_1_2, share_2_2, share_3_2)
    Note over P3: result_share_3 = f(share_1_3, share_2_3, share_3_3)
end

rect rgba(155, 89, 182, 0.15)
    Note over P1,P3: Round 2: Output Reconstruction
    P1 ->> P2: result_share_1
    P1 ->> P3: result_share_1
    P2 ->> P1: result_share_2
    P2 ->> P3: result_share_2
    P3 ->> P1: result_share_3
    P3 ->> P2: result_share_3
    Note over P1: Combine(result_share_1, result_share_2, result_share_3) → output
    Note over P2: Combine(...) → output
    Note over P3: Combine(...) → output
end
```

**Broadcast channel:** In many MPC protocols, "send to all" is a broadcast.
Use `par` blocks or annotate with `Note over P1: broadcast to all`.

**Code signals:** `round`, `broadcast`, `send_share`, `recv_share`,
`local_computation`, `reconstruct`, `output`.

---

## Threshold Signature (FROST / GG20 pattern)

**Parties:** Signers S1…St (threshold-of-n), Aggregator (A)
**Setup:** n parties each hold a signing key share

```
rect rgba(100, 149, 237, 0.15)
    Note over A: Coordinator selects t signers, distributes message m
    A ->> S1: sign_request(m, participants=[S1..St])
    A ->> S2: sign_request(m, participants=[S1..St])
    A ->> St: sign_request(m, participants=[S1..St])
end

rect rgba(46, 204, 113, 0.15)
    Note over S1..St: Round 1: Nonce Generation
    Note over S1: (d_1, e_1) = random nonces; D_1=g^d_1, E_1=g^e_1
    S1 ->> A: (D_1, E_1)
    Note over S2: (d_2, e_2) = random nonces
    S2 ->> A: (D_2, E_2)
    Note over St: (d_t, e_t) = random nonces
    St ->> A: (D_t, E_t)
end

rect rgba(155, 89, 182, 0.15)
    Note over A: Aggregate binding factors, compute group commitment R
    A ->> S1: commitment_list = [(D_i, E_i) for i in participants]
    A ->> S2: commitment_list
    A ->> St: commitment_list
end

rect rgba(241, 196, 15, 0.15)
    Note over S1..St: Round 2: Partial Signatures
    Note over S1: z_1 = d_1 + e_1·ρ_1 + λ_1·sk_1·c (partial sig)
    S1 ->> A: z_1
    Note over S2: z_2 = d_2 + e_2·ρ_2 + λ_2·sk_2·c
    S2 ->> A: z_2
    Note over St: z_t = ...
    St ->> A: z_t
end

Note over A: σ = (R, z_1 + z_2 + ... + z_t) — final signature
Note over A: Verify(group_pk, m, σ)
```

**Code signals:** `partial_sign`, `aggregate`, `nonce`, `commitment`,
`binding_factor`, `lagrange_coefficient`, `group_key`, `threshold_sign`.

---

## Reading Hints: Identifying Protocol Patterns in Code

| Code pattern | Protocol signal |
|---|---|
| `send_msg` / `recv_msg` loop with round counter | Round-based MPC |
| Two `CipherState` after `split()` | Noise protocol completion |
| `transcript` accumulated via hash | TLS-style transcript MAC |
| `chain_key` / `root_key` updated per message | Double Ratchet |
| `verify_prekey_signature` | X3DH signal protocol |
| `lagrange` / `interpolate` | Shamir / threshold |
| `partial_sig` aggregated after broadcast | Threshold signature |
| `commitment = H(value || nonce)` followed by `open` | Commit-reveal |
| `challenge` sent, `Sign(sk, challenge)` response | Challenge-response |
| `g^a` sent, `g^b` received, `g^(ab)` computed | Classic DH |
