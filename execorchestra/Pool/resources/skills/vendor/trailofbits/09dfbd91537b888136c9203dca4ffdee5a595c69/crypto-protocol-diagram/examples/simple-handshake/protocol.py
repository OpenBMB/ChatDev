# /// script
# requires-python = ">=3.12"
# dependencies = ["cryptography>=42.0"]
# ///
"""
Simple authenticated key exchange protocol (2 messages, 1 round trip).

Both parties hold long-term Ed25519 signing keys registered out-of-band.
The protocol establishes a forward-secret session key via ephemeral X25519 DH,
with mutual authentication via signatures over the transcript.

Message flow:
  1. Initiator → Responder : epk_i, sig_i
  2. Responder → Initiator : epk_r, sig_r
  Both derive: session_key = HKDF(DH(ek_i, epk_r), transcript)
"""

import os

from cryptography.hazmat.primitives import hashes, serialization  # type: ignore
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # type: ignore
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (  # type: ignore
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305  # type: ignore
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # type: ignore

# ---------------------------------------------------------------------------
# Key types
# ---------------------------------------------------------------------------


class StaticKeypair:
    """Long-term Ed25519 signing keypair (registered out-of-band)."""

    def __init__(self) -> None:
        self._sk = Ed25519PrivateKey.generate()
        self.pk = self._sk.public_key()

    def sign(self, message: bytes) -> bytes:
        return self._sk.sign(message)

    def public_bytes(self) -> bytes:
        return self.pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


class EphemeralKeypair:
    """Single-use X25519 DH keypair."""

    def __init__(self) -> None:
        self._sk = X25519PrivateKey.generate()
        self.pk = self._sk.public_key()

    def exchange(self, peer_epk: X25519PublicKey) -> bytes:
        return self._sk.exchange(peer_epk)

    def public_bytes(self) -> bytes:
        return self.pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


# ---------------------------------------------------------------------------
# Protocol messages
# ---------------------------------------------------------------------------


def _derive_session_key(dh_output: bytes, transcript: bytes) -> bytes:
    """HKDF-SHA256 over DH output, bound to the full transcript."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"session-key-v1",
    ).derive(dh_output + transcript)


def initiator_send_msg1(
    static: StaticKeypair,
) -> tuple[EphemeralKeypair, bytes]:
    """
    Initiator builds message 1.

    Returns (ephemeral_keypair, wire_bytes).
    wire_bytes = epk_i (32 bytes) || sig_i (64 bytes)
    """
    ek = EphemeralKeypair()
    epk_bytes = ek.public_bytes()
    sig = static.sign(b"msg1:" + epk_bytes)
    return ek, epk_bytes + sig


def responder_recv_msg1_send_msg2(
    msg1: bytes,
    initiator_pk: Ed25519PublicKey,
    static: StaticKeypair,
) -> tuple[bytes, bytes, bytes]:
    """
    Responder processes message 1 and builds message 2.

    Returns (session_key, msg2_wire_bytes, transcript).
    msg2_wire_bytes = epk_r (32 bytes) || sig_r (64 bytes)
    """
    epk_i_bytes, sig_i = msg1[:32], msg1[32:]

    # Verify initiator's ephemeral key is authentic.
    initiator_pk.verify(sig_i, b"msg1:" + epk_i_bytes)

    epk_i = X25519PublicKey.from_public_bytes(epk_i_bytes)

    ek_r = EphemeralKeypair()
    epk_r_bytes = ek_r.public_bytes()

    transcript = epk_i_bytes + epk_r_bytes
    sig_r = static.sign(b"msg2:" + transcript)

    dh_output = ek_r.exchange(epk_i)
    session_key = _derive_session_key(dh_output, transcript)

    return session_key, epk_r_bytes + sig_r, transcript


def initiator_recv_msg2(
    msg2: bytes,
    ek_i: EphemeralKeypair,
    responder_pk: Ed25519PublicKey,
    epk_i_bytes: bytes,
) -> bytes:
    """
    Initiator processes message 2 and derives the session key.

    Returns session_key.
    """
    epk_r_bytes, sig_r = msg2[:32], msg2[32:]

    transcript = epk_i_bytes + epk_r_bytes

    # Verify responder's contribution is authentic.
    responder_pk.verify(sig_r, b"msg2:" + transcript)

    epk_r = X25519PublicKey.from_public_bytes(epk_r_bytes)

    dh_output = ek_i.exchange(epk_r)
    return _derive_session_key(dh_output, transcript)


# ---------------------------------------------------------------------------
# Application data (post-handshake)
# ---------------------------------------------------------------------------


def encrypt(session_key: bytes, plaintext: bytes, nonce: bytes) -> bytes:
    return ChaCha20Poly1305(session_key).encrypt(nonce, plaintext, None)


def decrypt(session_key: bytes, ciphertext: bytes, nonce: bytes) -> bytes:
    return ChaCha20Poly1305(session_key).decrypt(nonce, ciphertext, None)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Out-of-band key registration
    initiator_static = StaticKeypair()
    responder_static = StaticKeypair()

    # --- Handshake ---
    ek_i, msg1 = initiator_send_msg1(initiator_static)
    epk_i_bytes = msg1[:32]

    sk_r, msg2, _ = responder_recv_msg1_send_msg2(
        msg1,
        initiator_static.pk,
        responder_static,
    )

    sk_i = initiator_recv_msg2(
        msg2,
        ek_i,
        responder_static.pk,
        epk_i_bytes,
    )

    if sk_i != sk_r:
        raise RuntimeError("session keys must match")
    print("Handshake complete. Session keys match.")

    # --- Application data ---
    nonce = os.urandom(12)
    ct = encrypt(sk_i, b"hello, responder", nonce)
    pt = decrypt(sk_r, ct, nonce)
    print(f"Decrypted: {pt}")
