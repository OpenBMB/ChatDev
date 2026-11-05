# Real-World Case Studies

Analysis of sharp edges in widely-used libraries. These aren't implementation bugs—they're design decisions that make secure usage difficult.

## GNU Multiple Precision Arithmetic Library (GMP)

GMP is used extensively for cryptographic implementations (RSA, Paillier, ElGamal, etc.) despite being fundamentally unsuitable for cryptography.

### Sharp Edge: Variable-Time Operations

**The Problem**: GMP operations are not constant-time. Timing varies based on input values.

```c
// DANGEROUS: Timing leaks secret exponent bits
mpz_powm(result, base, secret_exponent, modulus);

// Each bit of secret_exponent affects timing differently
// Attacker can recover secret_exponent via timing analysis
```

**Why This Matters**:
- Paillier encryption uses `mpz_powm` with secret keys
- RSA implementations using GMP leak private key bits
- Even "blinded" implementations often have residual timing leaks

**Detection Pattern**: Any use of GMP (`mpz_*` functions) with secret values:
- `mpz_powm`, `mpz_powm_sec` (the "sec" version is still not fully constant-time)
- `mpz_mul`, `mpz_mod` with secret operands
- `mpz_cmp` for secret comparison

**Real Vulnerabilities**:
- CVE-2018-16152: Timing attack on strongSwan IKEv2
- Numerous academic papers demonstrating key recovery from GMP-based crypto

### Sharp Edge: Memory Not Securely Cleared

```c
mpz_t secret_key;
mpz_init(secret_key);
// ... use secret_key ...
mpz_clear(secret_key);  // Memory NOT securely wiped
// Secret data may persist in freed memory
```

**The Problem**: `mpz_clear` doesn't zero memory before freeing. Secrets persist.

### Sharp Edge: Confusing Import/Export API

```c
// What does this do?
mpz_export(buf, &count, order, size, endian, nails, op);

// Parameters:
// - order: 1 = most significant word first, -1 = least significant
// - endian: 1 = big, -1 = little, 0 = native
// - nails: bits to skip at top of each word (?!)
```

**The Problem**: Seven parameters, three of which control byte ordering in different ways. Easy to get wrong, hard to verify correctness.

### Mitigation

For cryptographic use, prefer:
- **libsodium** for common operations
- **OpenSSL BIGNUM** (has constant-time variants)
- **libgmp with mpz_powm_sec** (partial mitigation, not complete)

---

## OpenSSL

The canonical example of a powerful but footgun-laden cryptographic library.

### Sharp Edge: SSL_CTX_set_verify Callback

```c
// DANGEROUS: Easy to write callback that always returns 1
SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, verify_callback);

int verify_callback(int preverify_ok, X509_STORE_CTX *ctx) {
    // Developer thinks: "I'll add logging here"
    log_certificate(ctx);
    return 1;  // OOPS: Always accepts, ignoring preverify_ok!
}
```

**The Problem**: The callback's return value determines whether verification succeeds. Developers often:
- Return 1 (success) unconditionally while "just adding logging"
- Forget that returning non-zero bypasses all verification
- Copy-paste examples that return 1 for "debugging"

**Correct Pattern**:
```c
int verify_callback(int preverify_ok, X509_STORE_CTX *ctx) {
    if (!preverify_ok) {
        // Log failure details
        log_verification_failure(ctx);
    }
    return preverify_ok;  // Preserve original decision
}
```

### Sharp Edge: Error Handling via ERR_get_error

```c
// DANGEROUS: Error easily ignored
EVP_EncryptFinal_ex(ctx, outbuf, &outlen);
// Did it succeed? Who knows!

// Correct but verbose:
if (EVP_EncryptFinal_ex(ctx, outbuf, &outlen) != 1) {
    unsigned long err = ERR_get_error();
    char buf[256];
    ERR_error_string_n(err, buf, sizeof(buf));
    // Handle error...
}
```

**The Problem**:
- Functions return 1 for success (not 0!)
- Errors accumulate in a thread-local queue
- Easy to forget to check, easy to check wrong way
- Error queue must be cleared or errors persist

### Sharp Edge: RAND_bytes vs RAND_pseudo_bytes

```c
// These look almost identical:
RAND_bytes(buf, len);        // Cryptographically secure
RAND_pseudo_bytes(buf, len); // NOT guaranteed secure!

// Worse: RAND_pseudo_bytes returns 1 even when insecure
int rc = RAND_pseudo_bytes(buf, len);
// rc == 1 means "success", not "cryptographically random"
// rc == 0 means "success but not crypto-strength" (!!)
// rc == -1 means "not supported"
```

**The Problem**: Function names differ by one word; return values are confusing; the insecure function is not clearly marked dangerous.

### Sharp Edge: Memory Ownership Confusion

```c
// Who frees this?
X509 *cert = SSL_get_peer_certificate(ssl);
// Answer: YOU do (it's a copy)

// Who frees this?
X509 *cert = SSL_get0_peer_certificate(ssl);  // OpenSSL 3.0+
// Answer: NOBODY (it's a reference)

// The difference: "get" vs "get0"
// This convention is NOT obvious or consistently applied
```

**The Problem**: Memory ownership indicated by subtle naming conventions that aren't documented together and aren't consistent across the API.

### Sharp Edge: EVP_CIPHER_CTX Reuse

```c
EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, key, iv);
EVP_EncryptUpdate(ctx, out, &outlen, in, inlen);
EVP_EncryptFinal_ex(ctx, out + outlen, &tmplen);

// DANGEROUS: Reusing ctx without reset
EVP_EncryptInit_ex(ctx, NULL, NULL, NULL, iv2);  // New IV only
// Some state from previous encryption may persist!
```

**The Problem**: Context reuse rules are complex and vary by cipher mode.

---

## Python's `pickle`

### Sharp Edge: Arbitrary Code Execution by Design

```python
import pickle

# DANGEROUS: Deserializes arbitrary Python objects
data = pickle.loads(untrusted_input)

# Attacker sends:
# b"cos\nsystem\n(S'rm -rf /'\ntR."
# Result: Executes shell command
```

**The Problem**: `pickle` is not a data format—it's a code execution format. There is no safe way to unpickle untrusted data, but:
- The function looks like a data parser
- The name suggests food preservation, not danger
- Many developers don't realize the risk

**Mitigation**: Use `json` for data. If you need pickle, use `hmac` to authenticate before unpickling (but even then, prefer safer formats).

---

## YAML Libraries

### Sharp Edge: Code Execution via Tags

```python
import yaml

# DANGEROUS: yaml.load() executes arbitrary code
data = yaml.load(untrusted_input)

# Attacker sends:
# !!python/object/apply:os.system ['rm -rf /']
```

**The Problem**: YAML's tag system allows arbitrary object instantiation. The "safe" loader is:
```python
data = yaml.safe_load(untrusted_input)  # Safe
data = yaml.load(untrusted_input, Loader=yaml.SafeLoader)  # Also safe
```

But the dangerous version is the obvious one (`yaml.load()`).

---

## PHP's `strcmp` for Password Comparison

### Sharp Edge: Type Juggling Bypass

```php
// DANGEROUS: Type juggling attack
if (strcmp($_POST['password'], $stored_password) == 0) {
    authenticate();
}

// Attacker sends: password[]=anything
// strcmp(array, string) returns NULL
// NULL == 0 is TRUE in PHP!
```

**The Problem**:
- `strcmp` returns `NULL` on type error, not `-1` or `1`
- PHP's `==` operator coerces `NULL` to `0`
- `NULL == 0` evaluates to `TRUE`
- Authentication bypassed

**Fix**:
```php
if (hash_equals($stored_hash, hash('sha256', $_POST['password']))) {
    // Use hash_equals for timing-safe comparison
    // AND proper password hashing (not shown)
}
```

---

## Analysis Template

When examining a library for sharp edges:

### Input → Expected Output

| Input | Expected | Actual | Vulnerability |
|-------|----------|--------|---------------|
| `verify_ssl=false` | Clear warning | Silent acceptance | Config cliff |
| `password=""` | Rejection | Login success | Empty bypass |
| `algorithm="none"` | Error | Signature skipped | Downgrade |
| `timeout=-1` | Error | Infinite timeout | Magic value |

### Library Comparison

| Feature | Dangerous Library | Safer Alternative |
|---------|------------------|-------------------|
| Bignum crypto | GMP | libsodium, OpenSSL BIGNUM |
| TLS | Raw OpenSSL | Higher-level wrappers |
| Serialization | pickle, YAML | JSON, protobuf |
| Password compare | strcmp | hash_equals, secrets.compare_digest |
