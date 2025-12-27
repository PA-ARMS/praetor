"""
API Endpoint Tests
Basic smoke tests for critical endpoints
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["status"] == "running"


def test_auth_login_missing_credentials():
    """Test login with missing credentials"""
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422  # Validation error


def test_auth_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "wrong"}
    )
    assert response.status_code == 401


def test_chat_requires_auth():
    """Test that chat endpoint requires authentication"""
    response = client.post(
        "/api/chat/query",
        json={"message": "test"}
    )
    assert response.status_code == 401 or response.status_code == 403


def test_forms_requires_auth():
    """Test that forms endpoint requires authentication"""
    response = client.post(
        "/api/forms/generate",
        json={"form_type": "test", "court": "test"}
    )
    assert response.status_code == 401 or response.status_code == 403


def test_monitoring_requires_auth():
    """Test that monitoring endpoints require authentication"""
    response = client.get("/api/monitoring/system")
    assert response.status_code == 401 or response.status_code == 403


def test_rate_limiting():
    """Test rate limiting (basic check)"""
    # Make multiple rapid requests
    responses = []
    for _ in range(100):
        response = client.get("/health")
        responses.append(response.status_code)
    
    # Health endpoint should not be rate limited
    # But we verify it still works
    assert all(status == 200 for status in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

