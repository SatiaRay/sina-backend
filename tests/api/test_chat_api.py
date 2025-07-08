import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Chat, ChatHistory
from api.chat import router
from fastapi import FastAPI
from database.models import get_db

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test app
app = FastAPI()

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def _override_db():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

app.include_router(router)
client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    # Create the database and tables
    Base.metadata.create_all(bind=engine)
    
    # Create a new session for the test
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after the test
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_chat(db_session):
    # Create a test chat
    chat = Chat(session_id="test-session-123")
    db_session.add(chat)
    db_session.commit()
    db_session.refresh(chat)
    return chat

@pytest.fixture(scope="function")
def test_chat_history(db_session, test_chat):
    # Create test chat history
    messages = [
        ChatHistory(
            chat_id=test_chat.id,
            role="user",
            body="Hello",
            created_at=datetime(2024, 3, 20, 10, 30, 0)
        ),
        ChatHistory(
            chat_id=test_chat.id,
            role="assistant",
            body="Hi! How can I help you?",
            created_at=datetime(2024, 3, 20, 10, 30, 5)
        )
    ]
    for msg in messages:
        db_session.add(msg)
    db_session.commit()
    return messages

def test_get_chat_history_success(db_session, test_chat, test_chat_history):
    response = client.get(f"/chat/history/{test_chat.session_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "assistant"
    assert data[0]["body"] == "Hi! How can I help you?"
    assert data[1]["role"] == "user"
    assert data[1]["body"] == "Hello"

def test_get_chat_history_with_limit(db_session, test_chat, test_chat_history):
    response = client.get(f"/chat/history/{test_chat.session_id}?limit=1")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "assistant"

def test_get_chat_history_with_offset(db_session, test_chat, test_chat_history):
    response = client.get(f"/chat/history/{test_chat.session_id}?offset=1")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "user"

def test_get_chat_history_nonexistent_session(db_session):
    response = client.get("/chat/history/nonexistent-session")
    assert response.status_code == 404
    assert "تاریخچه چت یافت نشد" in response.json()["detail"]["message"]

def test_get_chat_history_invalid_limit(db_session, test_chat):
    response = client.get(f"/chat/history/{test_chat.session_id}?limit=0")
    assert response.status_code == 422  # Validation error

def test_get_chat_history_invalid_offset(db_session, test_chat):
    response = client.get(f"/chat/history/{test_chat.session_id}?offset=-1")
    assert response.status_code == 422  # Validation error 