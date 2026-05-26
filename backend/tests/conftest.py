import json
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.security import get_current_user
from app.models import User

# Use an isolated, in-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# ── FIX FOR BUG 1: Force SQLite to handle dicts as JSON strings ──
@event.listens_for(engine, "connect")
def json_serializer_fallback(dbapi_connection, connection_record):
    """Enables fallback mappings so SQLite can serialize Python dicts smoothly."""
    def sqlite_serialize_dict(abstract_dict):
        return json.dumps(abstract_dict)
    
    # Register type adapter for dict formatting rules
    import sqlite3
    sqlite3.register_adapter(dict, sqlite_serialize_dict)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Initializes a clean database schema state before each test execution."""
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    """Provides a transactional database session block for test data initialization."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def mock_user(db_session):
    """Creates a mock user row structure inside the database setup."""
    user = User(id=1, email="testuser@qyverix.ai", password_hash="hashed_string")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def client(mock_user):
    """Generates a test client configuration pre-configured with authorized user routes."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()

@pytest.fixture
def unauthenticated_client():
    """Generates an unauthenticated client variant to validate security failures."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    # ── FIX FOR BUG 2: Correctly simulate standard unauthenticated credential rejections ──
    def override_get_current_user_unauthorized():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Not authenticated"
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user_unauthorized
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()