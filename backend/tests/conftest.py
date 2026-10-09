"""
Pytest configuration and shared fixtures for TruthLens backend tests.
"""

import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.core.database import Base, get_db
from app.main import app
from app.models.auth import User, Role
from app.core.security import get_password_hash


# =====================================================================
# Database Configuration
# =====================================================================

# Use in-memory SQLite for tests
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=None,  # Disable pooling for in-memory DB
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Provide test database session."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    # Override dependency
    def override_get_db():
        try:
            yield session
        finally:
            session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_client(db):
    """Provide FastAPI TestClient with database override."""
    return TestClient(app)


# =====================================================================
# Mock Redis
# =====================================================================

@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis for rate limiting tests."""
    mock_redis = MagicMock()
    mock_redis.zadd = MagicMock()
    mock_redis.zcard = MagicMock(return_value=0)
    mock_redis.zremrangebyscore = MagicMock()
    
    with patch("app.core.rate_limit.redis_client", mock_redis):
        yield mock_redis


# =====================================================================
# User Fixtures
# =====================================================================

@pytest.fixture
def test_user(db: Session):
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123"),
        role=Role.USER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db: Session):
    """Create an admin test user."""
    user = User(
        id=uuid4(),
        name="Admin User",
        email="admin@example.com",
        password_hash=get_password_hash("AdminPassword123"),
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user):
    """Generate JWT token for test user."""
    from app.core.security import create_access_token
    return create_access_token(subject=str(test_user.id), role=test_user.role.value)


@pytest.fixture
def auth_headers(auth_token):
    """Provide authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_token(admin_user):
    """Generate JWT token for admin user."""
    from app.core.security import create_access_token
    return create_access_token(subject=str(admin_user.id), role=admin_user.role.value)


@pytest.fixture
def admin_auth_headers(admin_token):
    """Provide authorization headers for admin requests."""
    return {"Authorization": f"Bearer {admin_token}"}
