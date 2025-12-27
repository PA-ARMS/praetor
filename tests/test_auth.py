"""
Authentication Tests
Tests for user authentication and authorization
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.main import app
from server.models import init_db, get_db, User, UserRole
from server.services.auth_service import get_password_hash

client = TestClient(app)

# Initialize test database
init_db()


@pytest.fixture
def test_user():
    """Create a test user"""
    db = next(get_db())
    try:
        # Check if user exists
        user = db.query(User).filter(User.username == "testuser").first()
        if not user:
            user = User(
                username="testuser",
                email="test@example.com",
                hashed_password=get_password_hash("testpass123"),
                full_name="Test User",
                role=UserRole.PARALEGAL,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def test_login_success(test_user):
    """Test successful login"""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["username"] == "testuser"


def test_login_wrong_password(test_user):
    """Test login with wrong password"""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_login_nonexistent_user():
    """Test login with nonexistent user"""
    response = client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "password"}
    )
    assert response.status_code == 401


def test_get_current_user(test_user):
    """Test getting current user info"""
    # First login
    login_response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    token = login_response.json()["access_token"]
    
    # Then get user info
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


def test_invalid_token():
    """Test access with invalid token"""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401 or response.status_code == 403


def test_missing_token():
    """Test access without token"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401 or response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

