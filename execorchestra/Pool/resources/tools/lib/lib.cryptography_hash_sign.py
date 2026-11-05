from _liblib import ok,err,a
from cryptography.hazmat.primitives import hashes
try:
    d=hashes.Hash(hashes.SHA256()); d.update(a(1).encode()); ok("lib.cryptography_hash_sign",algorithm="SHA256",digest=d.finalize().hex())
except Exception as e: err("lib.cryptography_hash_sign",str(e))
