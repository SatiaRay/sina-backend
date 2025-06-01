import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Document, CrawledDomain
from api.document import router, DocumentCreate, DocumentUpdate, VectorizeDocumentRequest
from fastapi import FastAPI
from database.models import get_db
from unittest.mock import patch, MagicMock
import json
import asyncio
from rq import Queue
from redis import Redis
import uuid
from fastapi import WebSocketDisconnect

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

app.dependency_overrides[get_db] = override_get_db
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
def mock_redis():
    with patch('api.document.Redis') as mock:
        yield mock

@pytest.fixture(scope="function")
def mock_queue(mock_redis):
    with patch('api.document.Queue') as mock:
        yield mock

@pytest.fixture(scope="function")
def mock_job():
    job = MagicMock()
    job.id = str(uuid.uuid4())
    job.meta = {}
    job.get_status.return_value = 'queued'
    job.is_finished = False
    job.is_failed = False
    return job

@pytest.fixture(scope="function")
def test_domain(db_session):
    domain = CrawledDomain(domain="example.com")
    db_session.add(domain)
    db_session.commit()
    return domain

@pytest.fixture(scope="function")
def test_document(db_session, test_domain):
    doc = Document(
        title="Test Document",
        html="<html>Test</html>",
        markdown="# Test",
        uri="https://example.com/test",
        domain_id=test_domain.id
    )
    db_session.add(doc)
    db_session.commit()
    return doc

def test_create_document(db_session, test_domain):
    # Test data
    document_data = {
        "title": "New Document",
        "html": "<html>New Test</html>",
        "markdown": "# New Test",
        "uri": "https://example.com/new",
        "domain_id": test_domain.id
    }
    
    # Make request
    response = client.post("/documents/", json=document_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == document_data["title"]
    assert data["html"] == document_data["html"]
    assert data["markdown"] == document_data["markdown"]
    assert data["uri"] == document_data["uri"]
    assert data["domain_id"] == test_domain.id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

def test_create_document_invalid_domain(db_session):
    # Test data with non-existent domain
    document_data = {
        "title": "New Document",
        "html": "<html>New Test</html>",
        "markdown": "# New Test",
        "uri": "https://example.com/new",
        "domain_id": 999  # Non-existent domain ID
    }
    
    # Make request
    response = client.post("/documents/", json=document_data)
    
    # Assertions
    assert response.status_code == 400
    assert "Domain not found" in response.json()["detail"]

def test_get_document(db_session, test_document):
    # Make request
    response = client.get(f"/documents/{test_document.id}")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_document.id
    assert data["title"] == test_document.title
    assert data["html"] == test_document.html
    assert data["markdown"] == test_document.markdown
    assert data["uri"] == test_document.uri
    assert data["domain_id"] == test_document.domain_id

def test_get_document_not_found(db_session):
    # Make request with non-existent ID
    response = client.get("/documents/999")
    
    # Assertions
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]

def test_update_document(db_session, test_document):
    # Test data
    update_data = {
        "title": "Updated Title",
        "html": "<html>Updated Test</html>",
        "markdown": "# Updated Test"
    }
    
    # Make request
    response = client.put(f"/documents/{test_document.id}", json=update_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == update_data["title"]
    assert data["html"] == update_data["html"]
    assert data["markdown"] == update_data["markdown"]
    assert data["id"] == test_document.id

def test_delete_document(db_session, test_document):
    # Make request
    response = client.delete(f"/documents/{test_document.id}")
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["message"] == "Document deleted successfully"
    
    # Verify document is deleted
    response = client.get(f"/documents/{test_document.id}")
    assert response.status_code == 404

def test_list_documents(db_session, test_document):
    # Make request
    response = client.get("/documents/")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["id"] == test_document.id

def test_vectorize_document(db_session, test_document, mock_queue, mock_job):
    # Setup mock queue
    mock_queue.return_value.enqueue.return_value = mock_job
    
    # Test data
    vectorize_data = {
        "html": "<html>Vector Test</html>",
        "metadata": {
            "source": "https://example.com/vector",
            "title": "Vector Test"
        }
    }
    
    # Make request
    response = client.post(f"/documents/{test_document.id}/vectorize", json=vectorize_data)
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "job_id" in data

@pytest.mark.asyncio
async def test_websocket_vectorize_status(mock_redis, mock_job):
    # Setup mock job
    mock_job.meta = {
        'progress': {'type': 'info', 'msg': 'Processing...'}
    }
    mock_job.get_status.return_value = 'started'
    mock_job.is_finished = False
    mock_job.is_failed = False

    # Mock Redis connection
    mock_redis.return_value = MagicMock()

    # Mock Job.fetch to return our mock job
    with patch('api.document.Job.fetch', return_value=mock_job), \
         patch('api.document.Redis', return_value=mock_redis.return_value):
        try:
            # Create WebSocket client
            with client.websocket_connect(f"/ws/documents/vectorize/{mock_job.id}") as websocket:
                # Receive progress update
                data = websocket.receive_json()
                assert data["event"] == "change_progress"
                assert data["progress"]["type"] == "info"
                assert data["progress"]["msg"] == "Processing..."
                assert data["status"] == "started"
        except WebSocketDisconnect:
            # This is expected as the WebSocket will close after sending the message
            pass

def test_toggle_document_vector_status(db_session, test_document):
    # First, test adding vector_id
    with patch('api.document.vector_store.add_documents') as mock_add:
        mock_add.return_value = ["vec_123"]
        response = client.post(f"/documents/{test_document.id}/toggle-vector")
        assert response.status_code == 200
        data = response.json()
        assert data["vector_id"] == "vec_123"

    # Then, test removing vector_id
    with patch('api.document.vector_store.delete_vector') as mock_delete:
        response = client.post(f"/documents/{test_document.id}/toggle-vector")
        assert response.status_code == 200
        data = response.json()
        assert data["vector_id"] is None
        mock_delete.assert_called_once_with("vec_123")

def test_get_document_by_vector_id(db_session, test_document):
    # First, add vector_id to document
    test_document.vector_id = "vec_123"
    db_session.commit()
    
    # Make request
    response = client.get("/documents/vector/vec_123")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_document.id
    assert data["vector_id"] == "vec_123"

def test_get_document_by_vector_id_not_found(db_session):
    # Make request with non-existent vector_id
    response = client.get("/documents/vector/nonexistent")
    
    # Assertions
    assert response.status_code == 404
    assert "No document found with vector_id" in response.json()["detail"]

def test_search_documents_by_title(db_session, test_document):
    # Make request
    response = client.get("/documents/search/title?query=Test")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["id"] == test_document.id 