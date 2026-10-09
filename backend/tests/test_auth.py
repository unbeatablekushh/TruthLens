import pytest
from sqlalchemy.orm import Session
from app.models.auth import User, RefreshToken, AuditLog, Role
from app.core.security import get_password_hash, verify_password, create_access_token, verify_access_token
from app.schemas.auth import UserCreate, UserLogin
from datetime import datetime, timedelta


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_get_password_hash(self):
        password = "TestPassword123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_password_correct(self):
        password = "TestPassword123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        password = "TestPassword123"
        wrong_password = "WrongPassword456"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) is False


class TestJWTTokens:
    """Test JWT token creation and verification"""
    
    def test_create_access_token(self):
        user_id = "test-user-id"
        token = create_access_token(subject=user_id, role="USER")
        assert token is not None
        assert isinstance(token, str)
        
    def test_verify_access_token_valid(self):
        user_id = "test-user-id"
        token = create_access_token(subject=user_id, role="USER")
        payload = verify_access_token(token)
        assert payload is not None
        assert payload.get("sub") == user_id
        assert payload.get("type") == "access"
        assert payload.get("role") == "USER"
    
    def test_verify_access_token_invalid(self):
        token = "invalid.token.here"
        payload = verify_access_token(token)
        assert payload is None


class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_register_success(self, test_client, db: Session):
        response = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["role"] == "USER"
        assert "password_hash" not in data
        
        # Verify user was created
        user = db.query(User).filter(User.email == "test@example.com").first()
        assert user is not None
        assert user.email == "test@example.com"
    
    def test_register_password_mismatch(self, test_client):
        response = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "DifferentPassword123"
            }
        )
        assert response.status_code == 400
        assert "Passwords do not match" in response.json()["detail"]
    
    def test_register_duplicate_email(self, test_client, db: Session):
        # Create first user
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User 1",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Try to create another with same email
        response = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User 2",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    def test_register_invalid_email(self, test_client):
        response = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "not-an-email",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_register_weak_password(self, test_client):
        response = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "weak",  # Too short
                "confirm_password": "weak"
            }
        )
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test user login endpoint"""
    
    def test_login_success(self, test_client, db: Session):
        # Register user first
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Login
        response = test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"
    
    def test_login_invalid_credentials(self, test_client):
        response = test_client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "WrongPassword123"
            }
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_login_wrong_password(self, test_client):
        # Register user first
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Try to login with wrong password
        response = test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword123"
            }
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]


class TestRefreshToken:
    """Test token refresh endpoint"""
    
    def test_refresh_token_success(self, test_client, db: Session):
        # Register and login
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )
        old_refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Verify token was rotated: check that the old token is now revoked in DB
        old_tokens = db.query(RefreshToken).filter(
            RefreshToken.revoked == True
        ).all()
        assert len(old_tokens) > 0
    
    def test_refresh_token_invalid(self, test_client):
        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid.token"}
        )
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]


class TestLogout:
    """Test logout endpoint"""
    
    def test_logout_success(self, test_client):
        # Register and login
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]
        
        # Logout
        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]


class TestGetMe:
    """Test GET /api/auth/me endpoint"""
    
    def test_get_me_success(self, test_client):
        # Register and login
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Get current user
        response = test_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["role"] == "USER"
    
    def test_get_me_unauthorized(self, test_client):
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401


class TestAuditLogging:
    """Test audit logging"""
    
    def test_audit_log_on_registration(self, test_client, db: Session):
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Check audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.event_type == "USER_REGISTERED"
        ).first()
        assert audit_log is not None
    
    def test_audit_log_on_login(self, test_client, db: Session):
        # Register user
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Login
        test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )
        
        # Check audit log
        audit_log = db.query(AuditLog).filter(
            AuditLog.event_type == "USER_LOGIN"
        ).first()
        assert audit_log is not None


class TestRoleBasedAccess:
    """Test role-based authorization"""
    
    def test_user_role_default(self, test_client, db: Session):
        test_client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPassword123",
                "confirm_password": "TestPassword123"
            }
        )
        
        # Check user role
        user = db.query(User).filter(User.email == "test@example.com").first()
        assert user.role == Role.USER
