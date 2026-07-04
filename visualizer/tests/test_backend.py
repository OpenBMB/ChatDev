# ══════════════════════════════════════════════════════════════════
#   test_backend.py — Comprehensive Backend Infrastructure Tests
#   Tests all 10 backend modules
# ══════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import pytest
import threading
import tempfile

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DB path for isolated tests
os.environ["CHATDEV_DB_PATH"] = os.path.join(tempfile.gettempdir(), "chatdev_test_suite.db")
os.environ["AUTH_ENABLED"] = "true"


# ══════════════════════════════════════════════════════════════
#   TEST 1: Authentication & Authorization
# ══════════════════════════════════════════════════════════════

class TestAuth:
    """Test JWT authentication, RBAC, and user management."""

    def test_generate_token(self):
        from visualizer.backend.auth import generate_token, verify_token
        tokens = generate_token("test_user", "admin")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert tokens["role"] == "admin"

    def test_verify_valid_token(self):
        from visualizer.backend.auth import generate_token, verify_token
        tokens = generate_token("test_user", "manager")
        payload = verify_token(tokens["access_token"])

        assert payload["sub"] == "test_user"
        assert payload["role"] == "manager"
        assert payload["iss"] == "chatdev-enterprise"

    def test_verify_expired_token(self):
        from visualizer.backend.auth import (
            _b64url_encode, _sign, AUTH_CONFIG
        )
        import json as _json

        # Create a token that expired 1 hour ago
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": "test", "role": "admin",
            "iss": AUTH_CONFIG["issuer"],
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,  # Expired
            "jti": "test123"
        }

        h = _b64url_encode(_json.dumps(header, separators=(",", ":")).encode())
        p = _b64url_encode(_json.dumps(payload, separators=(",", ":")).encode())
        sig = _sign(f"{h}.{p}")
        token = f"{h}.{p}.{sig}"

        from visualizer.backend.auth import verify_token
        with pytest.raises(ValueError, match="expired"):
            verify_token(token)

    def test_verify_invalid_signature(self):
        from visualizer.backend.auth import verify_token
        with pytest.raises(ValueError):
            verify_token("eyJ.eyJ.invalid_sig")

    def test_refresh_token(self):
        from visualizer.backend.auth import generate_token, refresh_access_token
        tokens = generate_token("test_user", "agent")
        new_tokens = refresh_access_token(tokens["refresh_token"])

        assert "access_token" in new_tokens
        assert new_tokens["role"] == "agent"

    def test_api_key_lifecycle(self):
        from visualizer.backend.auth import (
            create_api_key, verify_api_key, revoke_api_key
        )
        result = create_api_key("svc_user", "agent", "Test Key")
        key = result["api_key"]

        assert key.startswith("cdk_")
        info = verify_api_key(key)
        assert info["user_id"] == "svc_user"

        assert revoke_api_key(key) is True

        with pytest.raises(ValueError):
            verify_api_key(key)

    def test_user_registration_and_auth(self):
        from visualizer.backend.auth import (
            register_user, authenticate_user, delete_user
        )
        import secrets
        uid = f"test_{secrets.token_hex(4)}"

        register_user(uid, "SecurePass123!", "viewer", "Test User")
        tokens = authenticate_user(uid, "SecurePass123!")
        assert tokens["role"] == "viewer"

        with pytest.raises(ValueError, match="credentials"):
            authenticate_user(uid, "WrongPassword")

        delete_user(uid)

    def test_role_permissions(self):
        from visualizer.backend.auth import ROLE_PERMISSIONS
        assert "workflows:execute" in ROLE_PERMISSIONS["admin"]
        assert "workflows:execute" in ROLE_PERMISSIONS["agent"]
        assert "workflows:execute" not in ROLE_PERMISSIONS["viewer"]
        assert "system:config" in ROLE_PERMISSIONS["admin"]
        assert "system:config" not in ROLE_PERMISSIONS["manager"]

    def test_password_hashing(self):
        from visualizer.backend.auth import _hash_password
        hash1, salt1 = _hash_password("test_password")
        hash2, _ = _hash_password("test_password", salt1)
        assert hash1 == hash2

        hash3, _ = _hash_password("different_password", salt1)
        assert hash1 != hash3


# ══════════════════════════════════════════════════════════════
#   TEST 2: Database Layer
# ══════════════════════════════════════════════════════════════

class TestDatabase:
    """Test SQLite database operations."""

    def test_connection(self):
        from visualizer.backend.database import get_connection
        conn = get_connection()
        row = conn.execute("SELECT 1 as test").fetchone()
        assert row["test"] == 1

    def test_schema_initialized(self):
        from visualizer.backend.database import get_connection
        conn = get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        assert "executions" in table_names
        assert "audit_log" in table_names
        assert "webhook_events" in table_names

    def test_execution_crud(self):
        from visualizer.backend.database import ExecutionRepository
        import secrets
        exec_id = f"test_exec_{secrets.token_hex(4)}"

        ExecutionRepository.create(exec_id, "TestTeam", "Test task")
        result = ExecutionRepository.get(exec_id)
        assert result is not None
        assert result["team_name"] == "TestTeam"
        assert result["status"] == "running"

        ExecutionRepository.update_status(exec_id, "completed", total_tokens=1000)
        result = ExecutionRepository.get(exec_id)
        assert result["status"] == "completed"
        assert result["total_tokens"] == 1000

    def test_audit_log(self):
        from visualizer.backend.database import AuditRepository
        AuditRepository.log(
            user_id="test_user", action="test.action",
            resource_type="test", resource_id="123"
        )
        logs = AuditRepository.query(user_id="test_user", limit=5)
        assert len(logs) >= 1
        assert logs[0]["action"] == "test.action"

    def test_webhook_event_queue(self):
        from visualizer.backend.database import WebhookEventRepository
        event_id = WebhookEventRepository.enqueue(
            "test", "test_event", {"key": "value"}
        )
        assert event_id > 0

        pending = WebhookEventRepository.get_pending(limit=5)
        assert len(pending) >= 1

        WebhookEventRepository.mark_processed(event_id)
        stats = WebhookEventRepository.get_stats()
        assert "processed" in stats

    def test_context_manager(self):
        from visualizer.backend.database import get_db
        with get_db() as conn:
            conn.execute("SELECT 1")


# ══════════════════════════════════════════════════════════════
#   TEST 3: Rate Limiter
# ══════════════════════════════════════════════════════════════

class TestRateLimiter:
    """Test token bucket rate limiting."""

    def test_token_bucket_allows(self):
        from visualizer.backend.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=10, fill_rate=1.0)

        for _ in range(10):
            assert bucket.consume(1) is True

    def test_token_bucket_rejects(self):
        from visualizer.backend.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, fill_rate=0.1)

        for _ in range(5):
            bucket.consume(1)

        assert bucket.consume(1) is False

    def test_token_bucket_refills(self):
        from visualizer.backend.rate_limiter import TokenBucket
        bucket = TokenBucket(capacity=5, fill_rate=100.0)  # Fast refill

        for _ in range(5):
            bucket.consume(1)

        time.sleep(0.1)  # Wait for refill
        assert bucket.consume(1) is True

    def test_rate_limiter_check(self):
        from visualizer.backend.rate_limiter import RateLimiter
        limiter = RateLimiter()

        result = limiter.check("test_ip_123", "default")
        assert result["allowed"] is True
        assert result["remaining"] >= 0

    def test_rate_limiter_stats(self):
        from visualizer.backend.rate_limiter import RateLimiter
        limiter = RateLimiter()
        limiter.check("stat_ip", "default")
        stats = limiter.get_stats()
        assert stats["total_buckets"] >= 1

    def test_get_client_ip_forwarded(self):
        from visualizer.backend.rate_limiter import get_client_ip

        class MockRequest:
            headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            remote_addr = "127.0.0.1"

        assert get_client_ip(MockRequest()) == "1.2.3.4"

    def test_whitelist(self):
        from visualizer.backend.rate_limiter import WHITELIST_IPS
        assert "127.0.0.1" in WHITELIST_IPS
        assert "::1" in WHITELIST_IPS


# ══════════════════════════════════════════════════════════════
#   TEST 4: Health Checks
# ══════════════════════════════════════════════════════════════

class TestHealthChecks:
    """Test health check and readiness probes."""

    def test_uptime(self):
        from visualizer.backend.health import _get_uptime
        uptime = _get_uptime()
        assert uptime["seconds"] >= 0
        assert "human" in uptime
        assert "started_at" in uptime

    def test_database_check(self):
        from visualizer.backend.health import _check_database
        result = _check_database()
        assert result["status"] == "healthy"

    def test_filesystem_check(self):
        from visualizer.backend.health import _check_filesystem
        result = _check_filesystem()
        assert result["status"] in ("healthy", "warning")

    def test_python_env_check(self):
        from visualizer.backend.health import _check_python_env
        result = _check_python_env()
        assert result["status"] == "healthy"
        assert "python_version" in result

    def test_full_health_check(self):
        from visualizer.backend.health import run_health_checks
        result = run_health_checks()
        assert result["status"] in ("healthy", "degraded")
        assert "checks" in result
        assert "uptime" in result

    def test_memory_check(self):
        from visualizer.backend.health import _check_memory
        result = _check_memory()
        assert result["status"] in ("healthy", "warning", "skipped")


# ══════════════════════════════════════════════════════════════
#   TEST 5: Retry Engine & Circuit Breaker
# ══════════════════════════════════════════════════════════════

class TestRetryEngine:
    """Test retry, circuit breaker, and dead letter queue."""

    def test_retry_success_on_first(self):
        from visualizer.backend.retry_engine import retry

        call_count = {"n": 0}

        @retry(max_attempts=3, base_delay=0.01)
        def succeed():
            call_count["n"] += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count["n"] == 1

    def test_retry_success_after_failures(self):
        from visualizer.backend.retry_engine import retry

        call_count = {"n": 0}

        @retry(max_attempts=3, base_delay=0.01)
        def fail_twice():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("Temporary failure")
            return "recovered"

        assert fail_twice() == "recovered"
        assert call_count["n"] == 3

    def test_retry_exhausted(self):
        from visualizer.backend.retry_engine import retry

        @retry(max_attempts=2, base_delay=0.01)
        def always_fail():
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError, match="Permanent"):
            always_fail()

    def test_circuit_breaker_closed(self):
        from visualizer.backend.retry_engine import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_cb_1", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_circuit_breaker_opens(self):
        from visualizer.backend.retry_engine import (
            CircuitBreaker, CircuitState, CircuitBreakerOpenError
        )
        cb = CircuitBreaker("test_cb_2", failure_threshold=2, recovery_timeout=0.5)

        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "test")

    def test_circuit_breaker_recovery(self):
        from visualizer.backend.retry_engine import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_cb_3", failure_threshold=1,
                            recovery_timeout=0.1, success_threshold=1)

        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.call(lambda: "recovered")
        assert cb.state == CircuitState.CLOSED

    def test_dead_letter_queue(self):
        from visualizer.backend.retry_engine import DeadLetterQueue
        dlq = DeadLetterQueue(max_size=10)

        dlq.push("test_op", "test error", {"key": "value"})
        assert dlq.size() == 1

        items = dlq.peek(5)
        assert len(items) == 1
        assert items[0]["operation"] == "test_op"

        item = dlq.pop()
        assert item["error"] == "test error"
        assert dlq.size() == 0

    def test_dead_letter_queue_max_size(self):
        from visualizer.backend.retry_engine import DeadLetterQueue
        dlq = DeadLetterQueue(max_size=3)

        for i in range(5):
            dlq.push(f"op_{i}", f"error_{i}")

        assert dlq.size() == 3  # Oldest evicted

    def test_circuit_breaker_stats(self):
        from visualizer.backend.retry_engine import CircuitBreaker
        cb = CircuitBreaker("test_cb_stats")
        cb.call(lambda: "ok")
        stats = cb.get_stats()
        assert stats["total_calls"] == 1
        assert stats["state"] == "closed"


# ══════════════════════════════════════════════════════════════
#   TEST 6: Structured Logging
# ══════════════════════════════════════════════════════════════

class TestLogging:
    """Test structured logging and audit trail."""

    def test_correlation_id(self):
        from visualizer.backend.logging_engine import (
            set_correlation_id, get_correlation_id
        )
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"

    def test_json_formatter(self):
        from visualizer.backend.logging_engine import StructuredJsonFormatter
        import logging

        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="Test message", args=None, exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_audit_logger(self):
        from visualizer.backend.logging_engine import AuditLogger
        audit = AuditLogger()
        # Should not raise
        audit.log(
            user_id="test", action="test.action",
            resource_type="test", resource_id="123"
        )


# ══════════════════════════════════════════════════════════════
#   TEST 7: Response Cache
# ══════════════════════════════════════════════════════════════

class TestCache:
    """Test TTL cache and caching decorator."""

    def test_cache_set_get(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10, default_ttl=60)

        cache.set("key1", "value1")
        value, hit = cache.get("key1")
        assert hit is True
        assert value == "value1"

    def test_cache_miss(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10)

        value, hit = cache.get("nonexistent")
        assert hit is False
        assert value is None

    def test_cache_ttl_expiry(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10, default_ttl=0.05)  # 50ms TTL

        cache.set("expire_key", "expire_value")
        time.sleep(0.1)
        value, hit = cache.get("expire_key")
        assert hit is False

    def test_cache_lru_eviction(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=3, default_ttl=60)

        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict "a"

        _, hit_a = cache.get("a")
        assert hit_a is False

        _, hit_d = cache.get("d")
        assert hit_d is True

    def test_cache_invalidate_pattern(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10)

        cache.set("api:agents:1", "a1")
        cache.set("api:agents:2", "a2")
        cache.set("api:teams:1", "t1")

        count = cache.invalidate_pattern("api:agents")
        assert count == 2

        _, hit = cache.get("api:teams:1")
        assert hit is True

    def test_cache_stats(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10)

        cache.set("s1", "v1")
        cache.get("s1")  # Hit
        cache.get("s2")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == 50.0

    def test_cache_clear(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10)
        cache.set("x", 1)
        cache.set("y", 2)
        cleared = cache.clear()
        assert cleared == 2

    def test_cache_cleanup_expired(self):
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=10, default_ttl=0.01)
        cache.set("exp1", 1)
        cache.set("exp2", 2)
        time.sleep(0.05)
        cleaned = cache.cleanup_expired()
        assert cleaned >= 2


# ══════════════════════════════════════════════════════════════
#   TEST 8: Webhook Queue
# ══════════════════════════════════════════════════════════════

class TestWebhookQueue:
    """Test webhook signature verification and processing."""

    def test_slack_signature_verification(self):
        from visualizer.backend.webhook_queue import signature_verifier
        import hmac as _hmac, hashlib as _hashlib

        secret = "test_secret_key"
        timestamp = str(int(time.time()))
        body = '{"type":"event_callback"}'
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_sig = "v0=" + _hmac.new(
            secret.encode(), sig_basestring.encode(), _hashlib.sha256
        ).hexdigest()

        assert signature_verifier.verify_slack(
            body.encode(), expected_sig, timestamp, secret
        ) is True

    def test_slack_signature_failure(self):
        from visualizer.backend.webhook_queue import signature_verifier
        assert signature_verifier.verify_slack(
            b"body", "v0=wrong_sig", str(int(time.time())), "secret"
        ) is False

    def test_github_signature_verification(self):
        from visualizer.backend.webhook_queue import signature_verifier
        import hmac as _hmac, hashlib as _hashlib

        secret = "github_secret"
        body = b'{"action":"push"}'
        expected = "sha256=" + _hmac.new(
            secret.encode(), body, _hashlib.sha256
        ).hexdigest()

        assert signature_verifier.verify_github(body, expected, secret) is True

    def test_event_handler_registration(self):
        from visualizer.backend.webhook_queue import webhook_handler, _dispatch_event

        handled = {"called": False}

        @webhook_handler("test_source", "test_event")
        def test_handler(payload):
            handled["called"] = True
            return payload.get("data")

        results = _dispatch_event("test_source", "test_event", {"data": "hello"})
        assert handled["called"] is True
        assert len(results) >= 1

    def test_webhook_processor_stats(self):
        from visualizer.backend.webhook_queue import webhook_processor
        stats = webhook_processor.get_stats()
        assert "queue_size" in stats
        assert "processed" in stats


# ══════════════════════════════════════════════════════════════
#   TEST 9: API Docs & Versioning
# ══════════════════════════════════════════════════════════════

class TestAPIDocs:
    """Test OpenAPI spec generation."""

    def test_flask_rule_to_openapi(self):
        from visualizer.backend.api_docs import _flask_rule_to_openapi
        assert _flask_rule_to_openapi("/api/users/<user_id>") == "/api/users/{user_id}"
        assert _flask_rule_to_openapi("/api/items/<int:id>") == "/api/items/{id}"

    def test_extract_path_params(self):
        from visualizer.backend.api_docs import _extract_path_params
        params = _extract_path_params("/api/users/<user_id>/posts/<int:post_id>")
        assert len(params) == 2
        assert params[0]["name"] == "user_id"
        assert params[1]["name"] == "post_id"

    def test_api_config(self):
        from visualizer.backend.api_docs import API_CONFIG
        assert API_CONFIG["version"] == "1.0.0"
        assert "title" in API_CONFIG

    def test_document_endpoint_decorator(self):
        from visualizer.backend.api_docs import document_endpoint, _endpoint_docs

        @document_endpoint(summary="Test endpoint", tags=["Test"])
        def test_fn():
            pass

        assert "test_fn" in _endpoint_docs
        assert _endpoint_docs["test_fn"]["summary"] == "Test endpoint"


# ══════════════════════════════════════════════════════════════
#   TEST 10: Integration — Cross-Module
# ══════════════════════════════════════════════════════════════

class TestIntegration:
    """Cross-module integration tests."""

    def test_auth_token_flow(self):
        """Full authentication flow: register → login → verify → refresh."""
        from visualizer.backend.auth import (
            register_user, authenticate_user, verify_token,
            refresh_access_token, delete_user
        )
        import secrets
        uid = f"integ_{secrets.token_hex(4)}"

        register_user(uid, "StrongPass123!", "agent")
        tokens = authenticate_user(uid, "StrongPass123!")
        payload = verify_token(tokens["access_token"])
        assert payload["role"] == "agent"

        new_tokens = refresh_access_token(tokens["refresh_token"])
        new_payload = verify_token(new_tokens["access_token"])
        assert new_payload["sub"] == uid

        delete_user(uid)

    def test_database_audit_integration(self):
        """Verify audit logs are written to database."""
        from visualizer.backend.database import AuditRepository
        import secrets
        uid = f"audit_integ_{secrets.token_hex(4)}"

        AuditRepository.log(
            user_id=uid, action="integration.test",
            resource_type="test", resource_id="integ_001"
        )

        logs = AuditRepository.query(user_id=uid)
        assert len(logs) >= 1

    def test_retry_with_circuit_breaker(self):
        """Retry + circuit breaker combined."""
        from visualizer.backend.retry_engine import retry, CircuitBreaker

        cb = CircuitBreaker("integ_test", failure_threshold=5)
        call_count = {"n": 0}

        @retry(max_attempts=2, base_delay=0.01)
        def flaky_with_cb():
            call_count["n"] += 1
            def inner():
                if call_count["n"] < 2:
                    raise ConnectionError("Flaky")
                return "ok"
            return cb.call(inner)

        result = flaky_with_cb()
        assert result == "ok"

    def test_cache_with_ttl_stats(self):
        """Cache operations with stats verification."""
        from visualizer.backend.cache import TTLCache
        cache = TTLCache(max_size=100, default_ttl=300)

        for i in range(10):
            cache.set(f"integ_key_{i}", f"value_{i}")

        for i in range(5):
            cache.get(f"integ_key_{i}")

        cache.get("nonexistent_integ")

        stats = cache.get_stats()
        assert stats["size"] == 10
        assert stats["hits"] == 5
        assert stats["misses"] == 1


# ══════════════════════════════════════════════════════════════
#   Run All Tests
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
