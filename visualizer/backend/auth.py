# ══════════════════════════════════════════════════════════════════
#   auth.py — JWT Authentication & Authorization Middleware
#   Enterprise-grade auth layer for ChatDev Visualizer
#
#   Features:
#     - JWT token generation & validation (HMAC-SHA256)
#     - Role-based access control (RBAC): admin / manager / agent / viewer
#     - @login_required & @role_required decorators
#     - Session management with token refresh
#     - API key authentication for service-to-service calls
# ══════════════════════════════════════════════════════════════════

import os
import json
import time
import hmac
import hashlib
import base64
import secrets
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger("chatdev.auth")

# ── Configuration ──
AUTH_CONFIG = {
    "secret_key": os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32)),
    "token_expiry_hours": int(os.environ.get("JWT_EXPIRY_HOURS", "24")),
    "refresh_expiry_days": int(os.environ.get("JWT_REFRESH_DAYS", "7")),
    "algorithm": "HS256",
    "issuer": "chatdev-enterprise",
    "api_key_header": "X-API-Key",
    "auth_header": "Authorization",
    "auth_enabled": os.environ.get("AUTH_ENABLED", "true").lower() == "true",
}

# ── Role Hierarchy ──
ROLES = {
    "admin": 100,       # Full system access
    "manager": 75,      # Team management, workflow control
    "agent": 50,        # Agent operations, task execution
    "viewer": 25,       # Read-only access
}

ROLE_PERMISSIONS = {
    "admin": [
        "users:read", "users:write", "users:delete",
        "teams:read", "teams:write", "teams:delete",
        "workflows:read", "workflows:write", "workflows:execute", "workflows:delete",
        "system:config", "system:health",
        "knowledge:read", "knowledge:write", "knowledge:delete",
        "connectors:read", "connectors:write",
        "audit:read",
    ],
    "manager": [
        "users:read",
        "teams:read", "teams:write",
        "workflows:read", "workflows:write", "workflows:execute",
        "knowledge:read", "knowledge:write",
        "connectors:read", "connectors:write",
    ],
    "agent": [
        "teams:read",
        "workflows:read", "workflows:execute",
        "knowledge:read",
        "connectors:read",
    ],
    "viewer": [
        "teams:read",
        "workflows:read",
        "knowledge:read",
    ],
}


# ══════════════════════════════════════════════════════════════
#   JWT Token Engine (Pure Python — no PyJWT dependency)
# ══════════════════════════════════════════════════════════════

def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    """URL-safe base64 decode with padding restoration."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _sign(payload_str: str) -> str:
    """Create HMAC-SHA256 signature."""
    key = AUTH_CONFIG["secret_key"].encode("utf-8")
    signature = hmac.new(key, payload_str.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(signature)


def generate_token(user_id: str, role: str = "viewer", extra_claims: dict = None) -> dict:
    """
    Generate a JWT access token and refresh token.

    Args:
        user_id: Unique user identifier
        role: User role (admin/manager/agent/viewer)
        extra_claims: Additional claims to embed

    Returns:
        {"access_token": str, "refresh_token": str, "expires_at": str, "token_type": "Bearer"}
    """
    now = time.time()
    expiry = now + (AUTH_CONFIG["token_expiry_hours"] * 3600)
    refresh_expiry = now + (AUTH_CONFIG["refresh_expiry_days"] * 86400)

    # Access token payload
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "role": role,
        "iss": AUTH_CONFIG["issuer"],
        "iat": int(now),
        "exp": int(expiry),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    signature = _sign(signing_input)
    access_token = f"{signing_input}.{signature}"

    # Refresh token (separate JTI)
    refresh_payload = {
        "sub": user_id,
        "role": role,
        "iss": AUTH_CONFIG["issuer"],
        "iat": int(now),
        "exp": int(refresh_expiry),
        "jti": secrets.token_hex(16),
        "type": "refresh",
    }
    rp_b64 = _b64url_encode(json.dumps(refresh_payload, separators=(",", ":")).encode("utf-8"))
    r_signing = f"{header_b64}.{rp_b64}"
    r_signature = _sign(r_signing)
    refresh_token = f"{r_signing}.{r_signature}"

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": datetime.fromtimestamp(expiry).isoformat(),
        "token_type": "Bearer",
        "role": role,
    }


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.

    Returns:
        Decoded payload dict, or raises ValueError on failure.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature = parts
    signing_input = f"{header_b64}.{payload_b64}"

    expected_sig = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64))

    # Check expiry
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")

    # Check issuer
    if payload.get("iss") != AUTH_CONFIG["issuer"]:
        raise ValueError("Invalid token issuer")

    return payload


def refresh_access_token(refresh_token: str) -> dict:
    """
    Use a refresh token to generate a new access token.
    """
    payload = verify_token(refresh_token)
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    return generate_token(
        user_id=payload["sub"],
        role=payload.get("role", "viewer")
    )


# ══════════════════════════════════════════════════════════════
#   API Key Management
# ══════════════════════════════════════════════════════════════

_api_keys = {}  # {api_key: {"user_id": str, "role": str, "created": str}}
_api_key_lock = threading.Lock()

# Persistent storage path
_API_KEYS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".api_keys.json"
)


def _load_api_keys():
    """Load API keys from persistent storage."""
    global _api_keys
    if os.path.exists(_API_KEYS_FILE):
        try:
            with open(_API_KEYS_FILE, "r", encoding="utf-8") as f:
                _api_keys = json.load(f)
        except Exception:
            _api_keys = {}


def _save_api_keys():
    """Save API keys to persistent storage."""
    try:
        with open(_API_KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(_api_keys, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save API keys: {e}")


_load_api_keys()


def create_api_key(user_id: str, role: str = "agent", label: str = "") -> dict:
    """Generate a new API key for service-to-service auth."""
    key = f"cdk_{secrets.token_hex(24)}"
    with _api_key_lock:
        _api_keys[key] = {
            "user_id": user_id,
            "role": role,
            "label": label,
            "created": datetime.now().isoformat(),
        }
        _save_api_keys()
    return {"api_key": key, "user_id": user_id, "role": role, "label": label}


def verify_api_key(key: str) -> dict:
    """Verify an API key and return associated user info."""
    with _api_key_lock:
        info = _api_keys.get(key)
    if not info:
        raise ValueError("Invalid API key")
    return info


def revoke_api_key(key: str) -> bool:
    """Revoke an API key."""
    with _api_key_lock:
        if key in _api_keys:
            del _api_keys[key]
            _save_api_keys()
            return True
    return False


# ══════════════════════════════════════════════════════════════
#   User Store (in-memory + file-backed)
# ══════════════════════════════════════════════════════════════

_users = {}  # {user_id: {"password_hash": str, "role": str, "created": str, ...}}
_users_lock = threading.Lock()

_USERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".users.json"
)


def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return _b64url_encode(dk), salt


def _load_users():
    """Load users from file."""
    global _users
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r", encoding="utf-8") as f:
                _users = json.load(f)
        except Exception:
            _users = {}

    # Ensure default admin exists
    if "admin" not in _users:
        pw_hash, salt = _hash_password(os.environ.get("ADMIN_PASSWORD", "chatdev2026!"))
        _users["admin"] = {
            "password_hash": pw_hash,
            "salt": salt,
            "role": "admin",
            "display_name": "System Administrator",
            "created": datetime.now().isoformat(),
        }
        _save_users()


def _save_users():
    """Save users to file."""
    try:
        with open(_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(_users, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save users: {e}")


_load_users()


def register_user(user_id: str, password: str, role: str = "viewer",
                   display_name: str = "") -> dict:
    """Register a new user."""
    with _users_lock:
        if user_id in _users:
            raise ValueError(f"User '{user_id}' already exists")
        if role not in ROLES:
            raise ValueError(f"Invalid role: {role}")

        pw_hash, salt = _hash_password(password)
        _users[user_id] = {
            "password_hash": pw_hash,
            "salt": salt,
            "role": role,
            "display_name": display_name or user_id,
            "created": datetime.now().isoformat(),
        }
        _save_users()

    return {"user_id": user_id, "role": role, "display_name": display_name}


def authenticate_user(user_id: str, password: str) -> dict:
    """Authenticate user and return tokens."""
    with _users_lock:
        user = _users.get(user_id)
    if not user:
        raise ValueError("Invalid credentials")

    pw_hash, _ = _hash_password(password, user["salt"])
    if not hmac.compare_digest(pw_hash, user["password_hash"]):
        raise ValueError("Invalid credentials")

    tokens = generate_token(user_id, user["role"])
    tokens["display_name"] = user.get("display_name", user_id)
    return tokens


def list_users() -> list:
    """List all users (without sensitive data)."""
    with _users_lock:
        return [
            {
                "user_id": uid,
                "role": u["role"],
                "display_name": u.get("display_name", uid),
                "created": u.get("created"),
            }
            for uid, u in _users.items()
        ]


def delete_user(user_id: str) -> bool:
    """Delete a user."""
    with _users_lock:
        if user_id in _users and user_id != "admin":
            del _users[user_id]
            _save_users()
            return True
    return False


# ══════════════════════════════════════════════════════════════
#   Flask Decorators & Middleware
# ══════════════════════════════════════════════════════════════

def _extract_token_from_request(request_obj):
    """Extract token from Authorization header or API key header."""
    # Try Bearer token
    auth_header = request_obj.headers.get(AUTH_CONFIG["auth_header"], "")
    if auth_header.startswith("Bearer "):
        return ("jwt", auth_header[7:])

    # Try API key
    api_key = request_obj.headers.get(AUTH_CONFIG["api_key_header"], "")
    if api_key:
        return ("api_key", api_key)

    # Try query parameter (for WebSocket connections)
    token = request_obj.args.get("token", "")
    if token:
        return ("jwt", token)

    return (None, None)


def get_current_user(request_obj) -> dict:
    """
    Extract and validate the current user from request.
    Returns user payload or None.
    """
    if not AUTH_CONFIG["auth_enabled"]:
        return {"sub": "anonymous", "role": "admin", "auth_bypass": True}

    auth_type, credential = _extract_token_from_request(request_obj)

    if auth_type == "jwt":
        try:
            return verify_token(credential)
        except ValueError:
            return None
    elif auth_type == "api_key":
        try:
            info = verify_api_key(credential)
            return {"sub": info["user_id"], "role": info["role"], "auth_type": "api_key"}
        except ValueError:
            return None

    return None


def login_required(f):
    """
    Decorator: Require authentication for an endpoint.
    Injects `current_user` into kwargs.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify

        if not AUTH_CONFIG["auth_enabled"]:
            kwargs["current_user"] = {"sub": "anonymous", "role": "admin", "auth_bypass": True}
            return f(*args, **kwargs)

        user = get_current_user(request)
        if not user:
            return jsonify({
                "status": "error",
                "code": 401,
                "message": "Authentication required. Provide a valid Bearer token or API key.",
            }), 401

        kwargs["current_user"] = user
        return f(*args, **kwargs)

    return decorated


def role_required(*allowed_roles):
    """
    Decorator: Require specific role(s) for an endpoint.
    Must be used after @login_required.

    Usage:
        @app.route("/api/admin/users")
        @login_required
        @role_required("admin", "manager")
        def admin_users(current_user=None):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import jsonify

            user = kwargs.get("current_user", {})
            user_role = user.get("role", "viewer")

            if user.get("auth_bypass"):
                return f(*args, **kwargs)

            if user_role not in allowed_roles:
                return jsonify({
                    "status": "error",
                    "code": 403,
                    "message": f"Insufficient permissions. Required role: {', '.join(allowed_roles)}. Your role: {user_role}.",
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(permission: str):
    """
    Decorator: Require a specific permission.

    Usage:
        @app.route("/api/workflows/execute")
        @login_required
        @permission_required("workflows:execute")
        def execute_workflow(current_user=None):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import jsonify

            user = kwargs.get("current_user", {})
            user_role = user.get("role", "viewer")

            if user.get("auth_bypass"):
                return f(*args, **kwargs)

            user_perms = ROLE_PERMISSIONS.get(user_role, [])
            if permission not in user_perms:
                return jsonify({
                    "status": "error",
                    "code": 403,
                    "message": f"Permission denied: '{permission}' not granted to role '{user_role}'.",
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


# ══════════════════════════════════════════════════════════════
#   Auth Blueprint (Flask routes)
# ══════════════════════════════════════════════════════════════

def register_auth_routes(app):
    """Register authentication API routes on a Flask app."""
    from flask import request, jsonify

    @app.route("/api/auth/login", methods=["POST"])
    def auth_login():
        """Authenticate user and return JWT tokens."""
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", "").strip()
        password = data.get("password", "")

        if not user_id or not password:
            return jsonify({"status": "error", "message": "user_id and password required"}), 400

        try:
            tokens = authenticate_user(user_id, password)
            logger.info(f"🔐 User '{user_id}' logged in successfully")
            return jsonify({"status": "success", **tokens})
        except ValueError as e:
            logger.warning(f"🔒 Failed login attempt for '{user_id}'")
            return jsonify({"status": "error", "message": str(e)}), 401

    @app.route("/api/auth/register", methods=["POST"])
    def auth_register():
        """Register a new user (admin-only in production)."""
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", "").strip()
        password = data.get("password", "")
        role = data.get("role", "viewer")
        display_name = data.get("display_name", "")

        if not user_id or not password:
            return jsonify({"status": "error", "message": "user_id and password required"}), 400
        if len(password) < 8:
            return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400

        try:
            user = register_user(user_id, password, role, display_name)
            logger.info(f"👤 New user registered: {user_id} (role={role})")
            return jsonify({"status": "success", **user})
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/api/auth/refresh", methods=["POST"])
    def auth_refresh():
        """Refresh an access token using a refresh token."""
        data = request.get_json(silent=True) or {}
        refresh_tok = data.get("refresh_token", "")

        if not refresh_tok:
            return jsonify({"status": "error", "message": "refresh_token required"}), 400

        try:
            tokens = refresh_access_token(refresh_tok)
            return jsonify({"status": "success", **tokens})
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 401

    @app.route("/api/auth/me", methods=["GET"])
    @login_required
    def auth_me(current_user=None):
        """Get current user information."""
        return jsonify({
            "status": "success",
            "user": {
                "user_id": current_user.get("sub"),
                "role": current_user.get("role"),
                "permissions": ROLE_PERMISSIONS.get(current_user.get("role", "viewer"), []),
            }
        })

    @app.route("/api/auth/users", methods=["GET"])
    @login_required
    @role_required("admin")
    def auth_list_users(current_user=None):
        """List all users (admin only)."""
        return jsonify({"status": "success", "users": list_users()})

    @app.route("/api/auth/users/<user_id>", methods=["DELETE"])
    @login_required
    @role_required("admin")
    def auth_delete_user(user_id, current_user=None):
        """Delete a user (admin only)."""
        if delete_user(user_id):
            return jsonify({"status": "success", "message": f"User '{user_id}' deleted"})
        return jsonify({"status": "error", "message": "Cannot delete user"}), 400

    @app.route("/api/auth/api-keys", methods=["POST"])
    @login_required
    @role_required("admin", "manager")
    def auth_create_api_key(current_user=None):
        """Create a new API key."""
        data = request.get_json(silent=True) or {}
        result = create_api_key(
            user_id=current_user.get("sub"),
            role=data.get("role", "agent"),
            label=data.get("label", "")
        )
        return jsonify({"status": "success", **result})

    @app.route("/api/auth/api-keys/<key>", methods=["DELETE"])
    @login_required
    @role_required("admin")
    def auth_revoke_api_key(key, current_user=None):
        """Revoke an API key."""
        if revoke_api_key(key):
            return jsonify({"status": "success", "message": "API key revoked"})
        return jsonify({"status": "error", "message": "API key not found"}), 404

    logger.info("🔐 [Auth] Authentication routes registered")
