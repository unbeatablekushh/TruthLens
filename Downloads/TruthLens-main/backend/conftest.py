import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

# Mock the database connection before any app imports
os.environ['DATABASE_URL'] = "sqlite:///:memory:"

# Use SQLite in-memory database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mock Redis to avoid connection errors in tests
redis_mock = MagicMock()
redis_mock.zremrangebyscore.return_value = None
redis_mock.zcard.return_value = 0
redis_mock.zadd.return_value = None
redis_mock.expire.return_value = None

# Patch redis before importing app
with patch('app.core.rate_limit.redis_client', redis_mock):
    from app.core.database import Base, get_db
    from app.main import app
    from fastapi.testclient import TestClient

    # Create all tables
    Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def db():
    """Fixture that creates a fresh database for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        # Clean up
        db.close()
        # Clear all data
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()


@pytest.fixture
def test_client():
    """Fixture that provides a test client with mocked Redis."""
    with patch('app.core.rate_limit.redis_client', redis_mock):
        yield client
