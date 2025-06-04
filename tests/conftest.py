import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

# Add project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Now we can import database models
from database.models import Base

load_dotenv()

# Test database configuration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
TEST_DATABASE_ECHO = os.getenv("TEST_DATABASE_ECHO", "False").lower() == "true"

@pytest.fixture(scope="session")
def test_engine():
    """
    Create a test engine that will be used for all tests.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        poolclass=StaticPool,  # Use static pool for testing
        echo=TEST_DATABASE_ECHO
    )
    return engine

@pytest.fixture(scope="function")
def db(test_engine):
    """
    Create a fresh database for each test.
    The database is created and dropped for each test function.
    """
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create a new session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after the test
        Base.metadata.drop_all(bind=test_engine)
