"""
개선-30: E2E Test Suite for Seminar Studio APIs
================================================
Run:  python -m pytest tests/test_seminar_api.py -v
"""

import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="module")
def app():
    """Create a test Flask app."""
    os.environ["FLASK_ENV"] = "testing"
    from visualizer.app import app as _app
    _app.config["TESTING"] = True
    _app.config["SERVER_NAME"] = "localhost"
    return _app


@pytest.fixture(scope="module")
def client(app):
    """Create a test client."""
    return app.test_client()


class TestSeminarProductLifecycle:
    """Test full seminar product lifecycle: create → plan → generate → delete."""

    product_id = None

    def test_01_list_empty(self, client):
        """GET /api/seminar/products should return success."""
        resp = client.get("/api/seminar/products")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "products" in data

    def test_02_create_product(self, client):
        """POST /api/seminar/products should create a new seminar."""
        resp = client.post(
            "/api/seminar/products",
            json={"name": "테스트 세미나"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "product" in data
        assert data["product"]["name"] == "테스트 세미나"
        assert data["product"]["status"] == "draft"
        TestSeminarProductLifecycle.product_id = data["product"]["id"]

    def test_03_get_product(self, client):
        """GET /api/seminar/products/<id> should return the product."""
        pid = TestSeminarProductLifecycle.product_id
        if not pid:
            pytest.skip("No product_id from previous test")
        resp = client.get(f"/api/seminar/products/{pid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["product"]["id"] == pid

    def test_04_invalid_id_rejected(self, client):
        """Malformed or malicious product IDs are rejected.

        Valid IDs must match ^(sm|bc)_\\d{10,15}$ (enforced by the
        _validate_product_id decorator in seminar_routes_bp.py), so a
        well-formed-but-unknown-looking id is rejected with 400.

        A literal path-traversal attempt containing '/' never reaches that
        decorator at all: Flask's default <product_id> URL converter does
        not match path segments containing '/', so the route simply doesn't
        match and Flask returns 404 before any application code runs. That's
        an even stronger defense than a 400 from validation logic, so we
        assert on that behavior directly.
        """
        resp = client.get("/api/seminar/products/not-a-valid-id")
        assert resp.status_code == 400

        resp2 = client.get("/api/seminar/products/../../etc/passwd")
        assert resp2.status_code == 404

    def test_05_chat_advances_planning(self, client):
        """POST /api/seminar/products/<id>/chat should advance planning."""
        pid = TestSeminarProductLifecycle.product_id
        if not pid:
            pytest.skip("No product_id from previous test")
        resp = client.post(
            f"/api/seminar/products/{pid}/chat",
            json={"message": "AI/머신러닝, 직장인 대상"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "response" in data

    def test_06_update_spec(self, client):
        """PATCH /api/seminar/products/<id>/spec should update fields."""
        pid = TestSeminarProductLifecycle.product_id
        if not pid:
            pytest.skip("No product_id from previous test")
        resp = client.patch(
            f"/api/seminar/products/{pid}/spec",
            json={"speaker": "홍길동", "price": "50000원"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"

    def test_07_pagination(self, client):
        """GET /api/seminar/products?page=1&per_page=5 should return paginated results."""
        resp = client.get("/api/seminar/products?page=1&per_page=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "page" in data
        assert "per_page" in data
        assert "total" in data

    def test_08_reindex(self, client):
        """POST /api/seminar/reindex should rebuild index."""
        resp = client.post("/api/seminar/reindex")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"

    def test_09_delete_product(self, client):
        """DELETE /api/seminar/products/<id> should delete the product."""
        pid = TestSeminarProductLifecycle.product_id
        if not pid:
            pytest.skip("No product_id from previous test")
        resp = client.delete(f"/api/seminar/products/{pid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"

    def test_10_deleted_product_not_found(self, client):
        """GET deleted product should return 404."""
        pid = TestSeminarProductLifecycle.product_id
        if not pid:
            pytest.skip("No product_id from previous test")
        resp = client.get(f"/api/seminar/products/{pid}")
        assert resp.status_code == 404


class TestXSSPrevention:
    """Test XSS attack vectors are properly handled."""

    def test_create_with_script_tag(self, client):
        """Creating product with XSS payload should be safe."""
        resp = client.post(
            "/api/seminar/products",
            json={"name": "<script>alert('xss')</script>"},
            content_type="application/json",
        )
        # Should succeed but the name should be stored as-is
        # (rendering handles escaping)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "<script>" in data["product"]["name"]
        # Clean up
        pid = data["product"]["id"]
        client.delete(f"/api/seminar/products/{pid}")


class TestSchemaValidator:
    """Test schema validator module."""

    def test_validate_field_string(self):
        from visualizer.core.schema_validator import _validate_field
        errors = _validate_field("hello", "name", {"type": "string", "min_length": 1, "max_length": 10})
        assert errors == []

    def test_validate_field_too_short(self):
        from visualizer.core.schema_validator import _validate_field
        errors = _validate_field("", "name", {"type": "string", "min_length": 1})
        assert len(errors) > 0

    def test_validate_field_required(self):
        from visualizer.core.schema_validator import _validate_field
        errors = _validate_field(None, "name", {"required": True})
        assert len(errors) > 0

    def test_validate_field_enum(self):
        from visualizer.core.schema_validator import _validate_field
        errors = _validate_field("invalid", "status", {"type": "string", "enum": ["a", "b"]})
        assert len(errors) > 0
