"""Test API key authentication middleware."""
import pytest

pytest.importorskip("sqlalchemy", reason="sqlalchemy is required for app-backed auth middleware tests")


def test_health_no_auth_required(client):
    """Health endpoint should work without API key."""
    # Create client WITHOUT api key
    from fastapi.testclient import TestClient
    from app.main import app
    no_auth_client = TestClient(app)
    response = no_auth_client.get("/health")
    assert response.status_code == 200


def test_api_routes_require_auth():
    """API routes should return 401 without API key."""
    from fastapi.testclient import TestClient
    from app.main import app
    no_auth_client = TestClient(app)
    response = no_auth_client.get("/api/v1/jobs")
    assert response.status_code == 401


def test_api_routes_with_valid_key(client):
    """API routes should work with valid API key."""
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200


def test_api_routes_with_invalid_key():
    """API routes should return 401 with wrong key."""
    from fastapi.testclient import TestClient
    from app.main import app
    bad_client = TestClient(app, headers={"X-API-Key": "wrong-key"})
    response = bad_client.get("/api/v1/jobs")
    assert response.status_code == 401
