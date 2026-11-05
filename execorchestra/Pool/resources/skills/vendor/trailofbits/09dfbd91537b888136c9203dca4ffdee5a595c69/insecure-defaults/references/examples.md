# Insecure Defaults: Examples and Counter-Examples

This document provides detailed examples for each category in the Quick Verification Checklist, showing both vulnerable patterns (report these) and secure patterns (skip these).

## Fallback Secrets

### ❌ VULNERABLE - Report These

**Python: Environment variable with fallback**
```python
# File: src/auth/jwt.py
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

# Used in security context
def create_token(user_id):
    return jwt.encode({'user_id': user_id}, SECRET_KEY, algorithm='HS256')
```
**Why vulnerable:** App runs with known secret if `SECRET_KEY` is missing. Attacker can forge tokens.

**JavaScript: Logical OR fallback**
```javascript
// File: config/database.js
const DB_PASSWORD = process.env.DB_PASSWORD || 'admin123';

const pool = new Pool({
  user: 'admin',
  password: DB_PASSWORD,
  database: 'production'
});
```
**Why vulnerable:** Database accepts hardcoded password in production if env var missing.

**Ruby: fetch with default**
```ruby
# File: config/secrets.rb
Rails.application.credentials.secret_key_base =
  ENV.fetch('SECRET_KEY_BASE', 'fallback-secret-base')
```
**Why vulnerable:** Rails session encryption uses weak known key as fallback.

### ✅ SECURE - Skip These

**Fail-secure: Crashes without config**
```python
# File: src/auth/jwt.py
SECRET_KEY = os.environ['SECRET_KEY']  # Raises KeyError if missing

# App won't start without SECRET_KEY - fail-secure
```

**Explicit validation**
```javascript
// File: config/database.js
if (!process.env.DB_PASSWORD) {
  throw new Error('DB_PASSWORD environment variable required');
}
const DB_PASSWORD = process.env.DB_PASSWORD;
```

**Test fixtures (clearly scoped)**
```python
# File: tests/fixtures/auth.py
TEST_SECRET = 'test-secret-key-123'  # OK - test-only

# Usage in test
def test_token_creation():
    token = create_token('user1', secret=TEST_SECRET)
```

---

## Default Credentials

### ❌ VULNERABLE - Report These

**Hardcoded admin account**
```python
# File: src/models/user.py
def bootstrap_admin():
    """Create default admin account if none exists"""
    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin',
            password=hash_password('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
```
**Why vulnerable:** Default admin account created on first run with known credentials.

**API key in code**
```javascript
// File: src/integrations/payment.js
const STRIPE_API_KEY = process.env.STRIPE_KEY || 'sk_tes...';

const stripe = require('stripe')(STRIPE_API_KEY);
```
**Why vulnerable:** Uses test API key if env var missing. Might reach production.

**Database connection string**
```java
// File: DatabaseConfig.java
private static final String DB_URL = System.getenv().getOrDefault(
    "DATABASE_URL",
    "postgresql://admin:password@localhost:5432/prod"
);
```
**Why vulnerable:** Hardcoded database credentials as fallback.

### ✅ SECURE - Skip These

**Disabled default account**
```python
# File: src/models/user.py
def bootstrap_admin():
    """Admin account MUST be configured via environment"""
    username = os.environ['ADMIN_USERNAME']
    password = os.environ['ADMIN_PASSWORD']

    if not User.query.filter_by(username=username).first():
        admin = User(username=username, password=hash_password(password), role='admin')
        db.session.add(admin)
```

**Example/documentation credentials**
```bash
# File: README.md
## Setup

Configure your API key:
```bash
export STRIPE_KEY='sk_tes...'  # Example only
```
```

**Test fixture credentials**
```python
# File: tests/conftest.py
@pytest.fixture
def test_user():
    return User(username='test_user', password='test_pass')  # OK - test scope
```

---

## Fail-Open Security

### ❌ VULNERABLE - Report These

**Authentication disabled by default**
```python
# File: config/security.py
REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'false').lower() == 'true'

@app.before_request
def check_auth():
    if not REQUIRE_AUTH:
        return  # Skip auth check
    # ... auth logic
```
**Why vulnerable:** Default is no authentication. App runs insecurely if env var missing.

**CORS allows all origins**
```javascript
// File: server.js
const allowedOrigins = process.env.ALLOWED_ORIGINS || '*';

app.use(cors({ origin: allowedOrigins }));
```
**Why vulnerable:** Default allows requests from any origin. XSS/CSRF risk.

**Debug mode enabled by default**
```python
# File: config.py
DEBUG = os.getenv('DEBUG', 'true').lower() != 'false'  # Default: true

if DEBUG:
    app.config['DEBUG'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
```
**Why vulnerable:** Debug mode default. Stack traces leak sensitive info in production.

### ✅ SECURE - Skip These

**Authentication required by default**
```python
# File: config/security.py
REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'true').lower() == 'true'  # Default: true

# Or better - crash if not explicitly configured
REQUIRE_AUTH = os.environ['REQUIRE_AUTH'].lower() == 'true'
```

**CORS requires explicit configuration**
```javascript
// File: server.js
if (!process.env.ALLOWED_ORIGINS) {
  throw new Error('ALLOWED_ORIGINS must be configured');
}
const allowedOrigins = process.env.ALLOWED_ORIGINS.split(',');

app.use(cors({ origin: allowedOrigins }));
```

**Debug mode disabled by default**
```python
# File: config.py
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'  # Default: false
```

---

## Weak Crypto

### ❌ VULNERABLE - Report These

**MD5 for password hashing**
```python
# File: src/auth/passwords.py
import hashlib

def hash_password(password):
    """Hash user password"""
    return hashlib.md5(password.encode()).hexdigest()
```
**Why vulnerable:** MD5 is cryptographically broken. Rainbow tables exist. Use bcrypt/Argon2.

**DES encryption for sensitive data**
```java
// File: Encryption.java
public static byte[] encrypt(String data, byte[] key) {
    Cipher cipher = Cipher.getInstance("DES/ECB/PKCS5Padding");
    SecretKeySpec secretKey = new SecretKeySpec(key, "DES");
    cipher.init(Cipher.ENCRYPT_MODE, secretKey);
    return cipher.doFinal(data.getBytes());
}
```
**Why vulnerable:** DES has 56-bit keys (brute-forceable). ECB mode leaks patterns.

**SHA1 for signature verification**
```javascript
// File: webhooks.js
function verifySignature(payload, signature) {
  const hmac = crypto.createHmac('sha1', WEBHOOK_SECRET);
  const computed = hmac.update(payload).digest('hex');
  return computed === signature;
}
```
**Why vulnerable:** SHA1 collisions exist. Use SHA256 or better.

### ✅ SECURE - Skip These

**Weak crypto for non-security checksums**
```python
# File: src/utils/cache.py
import hashlib

def cache_key(data):
    """Generate cache key - not security-sensitive"""
    return hashlib.md5(data.encode()).hexdigest()  # OK - just for cache lookup
```

**Modern crypto for passwords**
```python
# File: src/auth/passwords.py
import bcrypt

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

**Strong encryption**
```java
// File: Encryption.java
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
// 256-bit key, authenticated encryption
```

---

## Permissive Access

### ❌ VULNERABLE - Report These

**File permissions world-writable**
```python
# File: src/storage/files.py
def create_secure_file(path):
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o666)  # rw-rw-rw-
    return fd
```
**Why vulnerable:** Any user can write to file. Should be 0o600 or 0o644.

**S3 bucket public by default**
```python
# File: infrastructure/storage.py
def create_storage_bucket(name):
    bucket = s3.create_bucket(
        Bucket=name,
        ACL='public-read'  # Publicly readable by default
    )
```
**Why vulnerable:** Sensitive data exposed publicly. Should require explicit configuration.

**API allows any origin**
```python
# File: app.py
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response
```
**Why vulnerable:** CORS misconfiguration. Allows credential theft from any site.

### ✅ SECURE - Skip These

**Explicitly configured permissiveness with justification**
```python
# File: src/storage/public_assets.py
def create_public_asset(path):
    """Create world-readable asset for CDN distribution"""
    # Intentionally public - static assets only
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o644)
    return fd
```

**Restrictive by default**
```python
# File: infrastructure/storage.py
def create_storage_bucket(name, public=False):
    acl = 'public-read' if public else 'private'
    if public:
        logger.warning(f'Creating PUBLIC bucket: {name}')
    bucket = s3.create_bucket(Bucket=name, ACL=acl)
```

---

## Debug Features

### ❌ VULNERABLE - Report These

**Stack traces in API responses**
```python
# File: app.py
@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({
        'error': str(error),
        'traceback': traceback.format_exc()  # Leaks internal paths, library versions
    }), 500
```
**Why vulnerable:** Exposes internal implementation details to attackers.

**GraphQL introspection enabled**
```javascript
// File: server.js
const server = new ApolloServer({
  typeDefs,
  resolvers,
  introspection: true,  // Enabled in production
  playground: true
});
```
**Why vulnerable:** Attackers can discover entire API schema, including admin-only fields.

**Verbose error messages**
```java
// File: UserController.java
catch (SQLException e) {
    return ResponseEntity.status(500).body(
        "Database error: " + e.getMessage()  // Leaks table names, constraints
    );
}
```
**Why vulnerable:** SQL error messages reveal database structure.

### ✅ SECURE - Skip These

**Debug features in logging only**
```python
# File: app.py
@app.errorhandler(Exception)
def handle_error(error):
    logger.exception('Request failed', exc_info=error)  # Logs full trace
    return jsonify({'error': 'Internal server error'}), 500  # Generic to user
```

**Environment-aware debug settings**
```javascript
// File: server.js
const server = new ApolloServer({
  typeDefs,
  resolvers,
  introspection: process.env.NODE_ENV !== 'production',
  playground: process.env.NODE_ENV !== 'production'
});
```

**Generic user-facing errors**
```java
// File: UserController.java
catch (SQLException e) {
    logger.error("Database error", e);  // Full details to logs
    return ResponseEntity.status(500).body("Unable to process request");  // Generic
}
```
